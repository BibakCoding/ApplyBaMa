# dashboard/views.py
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
import secrets
import string

from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from core.models import User, StudentProfile, Application, University, Program, Country, City
from .forms import (
    PersonalInfoForm, ContactInfoForm, ProfileImageForm,
    StudentProfileForm, CustomPasswordChangeForm,
    ApplicationForm, AddStudentForm
)

def get_managed_students(user):
    """Returns student IDs managed by an Agent or a Company's agents."""
    if user.user_type == User.UserType.AGENT:
        return Application.objects.filter(agent=user).values_list('student_id', flat=True).distinct()
    elif user.user_type == User.UserType.COMPANY:
        try:
            company_profile = user.company_profile
            agent_users = User.objects.filter(agent_profile__agency=company_profile)
            return Application.objects.filter(agent__in=agent_users).values_list('student_id', flat=True).distinct()
        except Exception:
            return []
    return []

@login_required
def dashboard_main(request):
    return render(request, "dashboard/main.html", context={"user": request.user})

@login_required
def dashboard_content(request, page):
    """Handles GET requests to render SPA fragments"""
    content_map = {
        'welcome': 'dashboard/fragments/welcome.html',
        'profile': 'dashboard/fragments/profile.html',
        'universities': 'dashboard/fragments/universities.html',
        'programs': 'dashboard/fragments/programs.html',
        'new_application': 'dashboard/fragments/new_application.html',
        'my_applications': 'dashboard/fragments/my_applications.html',
        'my_students': 'dashboard/fragments/my_students.html',
        'application_detail': 'dashboard/fragments/application_detail.html',
        'university_detail': 'dashboard/fragments/university_detail.html',
    }

    if page not in content_map:
        messages.error(request, _('Page not found.'))
        return redirect('dashboard')

    protected_pages = ['new_application', 'my_students']
    if page in protected_pages:
        user = request.user
        if not (user.user_type in ['company', 'agent'] or (user.user_type == 'student' and user.is_representative)):
            messages.error(request, _('You do not have permission to access this page.'))
            return redirect('dashboard')

    context = {"user": request.user}

    if page == 'profile':
        user = request.user
        try:
            student_profile = user.student_profile
        except StudentProfile.DoesNotExist:
            student_profile = None
        context['personal_form'] = PersonalInfoForm(instance=user)
        context['contact_form'] = ContactInfoForm(instance=user)
        context['image_form'] = ProfileImageForm(instance=user)
        context['password_form'] = CustomPasswordChangeForm(user=user)
        context['student_form'] = StudentProfileForm(instance=student_profile) if student_profile else None

    elif page == 'universities':
        qs = University.objects.all().select_related('country', 'city')
        search_query = request.GET.get('search', '')
        country_id = request.GET.get('country', '')
        sector = request.GET.get('sector', '')

        if search_query: qs = qs.filter(name__icontains=search_query)
        if country_id: qs = qs.filter(country_id=country_id)
        if sector: qs = qs.filter(sector=sector)

        paginator = Paginator(qs, 12)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['page_obj'] = page_obj
        countries_with_universities = Country.objects.filter(universities__isnull=False).distinct().order_by('name')
        context['countries'] = countries_with_universities
        context['filters'] = {'search': search_query, 'country': country_id, 'sector': sector}

    elif page == 'programs':
        qs = Program.objects.all().select_related('university', 'faculty')
        search_query = request.GET.get('search', '')
        university_id = request.GET.get('university', '')
        degree = request.GET.get('degree', '')
        status = request.GET.get('status', '')

        if search_query: qs = qs.filter(name__icontains=search_query)
        if university_id: qs = qs.filter(university_id=university_id)
        if degree: qs = qs.filter(degree=degree)
        if status: qs = qs.filter(status=status)

        paginator = Paginator(qs, 12)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['page_obj'] = page_obj
        context['universities_filter'] = University.objects.all().order_by('name')
        context['degrees'] = Program.DEGREE_CHOICES
        context['statuses'] = Program.StatusChoices.choices
        context['filters'] = {'search': search_query, 'university': university_id, 'degree': degree, 'status': status}

    elif page == 'university_detail':
        uni_id = request.GET.get('id')
        if uni_id:
            uni = get_object_or_404(University, pk=uni_id)
            programs = Program.objects.filter(university=uni).select_related('faculty')
            context['uni'] = uni
            context['programs'] = programs
        else:
            return redirect('dashboard')

    elif page == 'my_applications':
        if request.user.user_type == User.UserType.AGENT:
            applications = Application.objects.filter(agent=request.user).select_related('student', 'program', 'program__university').order_by('-created_at')
        else:
            applications = Application.objects.filter(student=request.user).select_related('program', 'program__university', 'agent').order_by('-created_at')
        context['applications'] = applications

    elif page == 'my_students':
        student_ids = get_managed_students(request.user)
        students = User.objects.filter(id__in=student_ids)
        context['students'] = students
        context['add_student_form'] = AddStudentForm()

    elif page == 'new_application':
        student_ids = get_managed_students(request.user)
        context['form'] = ApplicationForm(student_queryset=student_ids)

    elif page == 'application_detail':
        pk = request.GET.get('id')
        if pk:
            app = get_object_or_404(Application, pk=pk)
            if request.user != app.agent and request.user != app.student:
                messages.error(request, _("Permission denied."))
                return redirect('dashboard')
            context['app'] = app
        else:
            return redirect('dashboard')

    return render(request, content_map[page], context=context)

@login_required
def get_cities_by_country(request):
    country_id = request.GET.get('country_id')
    if country_id:
        try:
            cities = City.objects.filter(country_id=country_id).order_by('name')
            cities_data = [{'id': city.id, 'name': city.name} for city in cities]
            return JsonResponse({'cities': cities_data})
        except Exception as e:
            return JsonResponse({'cities': [], 'error': str(e)})
    return JsonResponse({'cities': []})

@login_required
def profile_view(request):
    if request.method != 'POST':
        return redirect('dashboard')

    user = request.user
    student_profile = getattr(user, 'student_profile', None)
    form_type = request.POST.get('form_type')

    if form_type == 'personal_info':
        form = PersonalInfoForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return _success_response(_("Personal information updated successfully."))
        return _form_error_response(form)

    elif form_type == 'contact_info':
        form = ContactInfoForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return _success_response(_("Contact information updated successfully."))
        return _form_error_response(form)

    elif form_type == 'profile_image':
        form = ProfileImageForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return _success_response(_("Profile image updated successfully."))
        return _form_error_response(form)

    elif form_type == 'password_change':
        form = CustomPasswordChangeForm(user=user, data=request.POST)
        if form.is_valid():
            updated_user = form.save()
            update_session_auth_hash(request, updated_user)
            return _success_response(_("Password changed successfully."))
        return _form_error_response(form)

    elif form_type == 'student_profile' and student_profile:
        form = StudentProfileForm(request.POST, instance=student_profile)
        if form.is_valid():
            form.save()
            return _success_response(_("Student profile updated successfully."))
        return _form_error_response(form)

    return JsonResponse({'success': False, 'errors': [_('Invalid form type.')]})

def _success_response(message):
    return JsonResponse({'success': True, 'message': str(message)})

def _form_error_response(form):
    errors = []
    for field, error_list in form.errors.items():
        for error in error_list:
            errors.append(f"{field.replace('_', ' ').title()}: {error}")
    return JsonResponse({'success': False, 'errors': errors})

@login_required
def application_action(request, pk):
    app = get_object_or_404(Application, pk=pk)
    if request.user != app.agent and request.user != app.student:
        return JsonResponse({'success': False, 'message': 'Permission denied.'})

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_step':
            new_step = request.POST.get('step')
            if new_step in [str(c[0]) for c in app.StepChoices.choices]:
                app.step = int(new_step)
                app.save()
                return JsonResponse({'success': True, 'message': _('Step updated.')})
        elif action == 'delete':
            app.delete()
            return JsonResponse({'success': True, 'message': _('Application deleted.')})

    return JsonResponse({'success': False, 'message': 'Invalid action.'})

@login_required
def generate_password(request):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for i in range(12))
    return JsonResponse({'password': password})

@login_required
def submit_new_application(request):
    # Allowed for both AGENT and COMPANY
    if request.method == 'POST' and request.user.user_type in [User.UserType.AGENT, User.UserType.COMPANY]:
        student_ids = get_managed_students(request.user)
        form = ApplicationForm(request.POST, request.FILES, student_queryset=student_ids)
        if form.is_valid():
            application = form.save(commit=False)
            application.agent = request.user
            application.save()
            return JsonResponse({'success': True, 'message': _('Application created successfully.'), 'redirect': True})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    return JsonResponse({'success': False, 'message': _('Invalid request.')})

@login_required
@ratelimit(key='ip', rate='10/h', method='POST', block=True)
@ratelimit(key='user', rate='5/h', method='POST', block=True)
def submit_add_student(request):
    # Allowed for both AGENT and COMPANY
    if request.method == 'POST' and request.user.user_type in [User.UserType.AGENT, User.UserType.COMPANY]:
        form = AddStudentForm(request.POST)
        if form.is_valid():
            existing_count = Application.objects.filter(agent=request.user).count()
            if existing_count >= 100:
                return JsonResponse({
                    'success': False,
                    'message': _('You have reached the maximum number of students (100). Please contact support.')
                })

            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                user_type=User.UserType.DEFAULT
            )
            StudentProfile.objects.create(user=user, stage='freshman')
            Application.objects.create(agent=request.user, student=user)
            return JsonResponse({'success': True, 'message': _('Student added successfully.')})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    return JsonResponse({'success': False, 'message': _('Invalid request.')})

@login_required
def program_apply_request(request):
    if request.method == 'POST':
        program_id = request.POST.get('program_id')
        if not program_id:
            return JsonResponse({'success': False, 'message': str(_('Invalid request.'))})

        program = get_object_or_404(Program, pk=program_id)
        user = request.user

        subject = f"Apply Request: {user.get_full_name() or user.username} → {program.name}"
        message = (
            f"A student has requested to apply for a program.\n\n"
            f"Student: {user.get_full_name() or user.username}\n"
            f"Email: {user.email}\n"
            f"Username: {user.username}\n"
            f"Program: {program.name}\n"
            f"University: {program.university.name}\n"
            f"Degree: {program.get_degree_display()}\n"
            f"Status: {program.get_status_display()}\n\n"
            f"Please contact the student to proceed."
        )

        try:
            admin_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'admin@applybama.com'
            send_mail(subject, message, admin_email, [admin_email], fail_silently=False)
            return JsonResponse({'success': True, 'message': str(_('Your request has been sent! Our team will contact you soon.'))})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(_('Failed to send request. Please try again.'))})

    return JsonResponse({'success': False, 'message': str(_('Invalid request.'))})
