# dashboard/views.py
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
import secrets
import string

from core.models import User, StudentProfile, Application, University, Program, Country
from .forms import (
    PersonalInfoForm, ContactInfoForm, ProfileImageForm,
    StudentProfileForm, CustomPasswordChangeForm,
    ApplicationForm, AddStudentForm
)

@login_required
def dashboard_main(request):
    """Renders the main dashboard layout (sidebar + empty content container)"""
    return render(request, "dashboard/main.html", context={"user": request.user})

@login_required
def dashboard_content(request, page):
    """Renders the specific inner fragment requested via AJAX"""
    content_map = {
        'welcome': 'dashboard/fragments/welcome.html',
        'profile': 'dashboard/fragments/profile.html',
        'universities': 'dashboard/fragments/universities.html',
        'programs': 'dashboard/fragments/programs.html',
        'new_application': 'dashboard/fragments/new_application.html',
        'my_applications': 'dashboard/fragments/my_applications.html',
        'my_students': 'dashboard/fragments/my_students.html',
        'application_detail': 'dashboard/fragments/application_detail.html',
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

    # --- UNIVERSITIES LOGIC ---
    if page == 'universities':
        qs = University.objects.all().select_related('country', 'city')
        search_query = request.GET.get('search', '')
        country_id = request.GET.get('country', '')
        sector = request.GET.get('sector', '')

        if search_query:
            qs = qs.filter(name__icontains=search_query)
        if country_id:
            qs = qs.filter(country_id=country_id)
        if sector:
            qs = qs.filter(sector=sector)

        paginator = Paginator(qs, 12) # 12 universities per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['page_obj'] = page_obj
        context['countries'] = Country.objects.all().order_by('name')
        context['filters'] = {
            'search': search_query,
            'country': country_id,
            'sector': sector,
            'page': page_number or 1
        }

    # --- PROGRAMS LOGIC ---
    elif page == 'programs':
        qs = Program.objects.all().select_related('university', 'faculty')
        search_query = request.GET.get('search', '')
        university_id = request.GET.get('university', '')
        degree = request.GET.get('degree', '')
        status = request.GET.get('status', '')

        if search_query:
            qs = qs.filter(name__icontains=search_query)
        if university_id:
            qs = qs.filter(university_id=university_id)
        if degree:
            qs = qs.filter(degree=degree)
        if status:
            qs = qs.filter(status=status)

        paginator = Paginator(qs, 12) # 12 programs per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['page_obj'] = page_obj
        context['universities_filter'] = University.objects.all().order_by('name')
        context['degrees'] = Program.DEGREE_CHOICES
        context['statuses'] = Program.StatusChoices.choices
        context['filters'] = {
            'search': search_query,
            'university': university_id,
            'degree': degree,
            'status': status,
            'page': page_number or 1
        }

    elif page == 'my_applications':
        if request.user.user_type == User.UserType.AGENT:
            applications = Application.objects.filter(agent=request.user).order_by('-created_at')
        else:
            applications = Application.objects.filter(student=request.user).order_by('-created_at')
        context['applications'] = applications

    elif page == 'my_students':
        student_ids = Application.objects.filter(agent=request.user).values_list('student_id', flat=True).distinct()
        students = User.objects.filter(id__in=student_ids)
        context['students'] = students
        context['add_student_form'] = AddStudentForm()

    elif page == 'new_application':
        context['form'] = ApplicationForm(agent=request.user)

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
    if request.method == 'POST' and request.user.user_type == User.UserType.AGENT:
        form = ApplicationForm(request.POST, request.FILES, agent=request.user)
        if form.is_valid():
            application = form.save(commit=False)
            application.agent = request.user
            application.save()
            return JsonResponse({'success': True, 'message': _('Application created successfully.'), 'redirect': True})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    return JsonResponse({'success': False, 'message': _('Invalid request.')})

@login_required
def submit_add_student(request):
    if request.method == 'POST' and request.user.user_type == User.UserType.AGENT:
        form = AddStudentForm(request.POST)
        if form.is_valid():
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
def profile_view(request):
    if request.method == 'GET' and request.headers.get('x-requested-with') != 'XMLHttpRequest':
        from django.urls import reverse
        return redirect(f"{reverse('dashboard')}?page=profile")

    user = request.user
    student_profile = getattr(user, 'student_profile', None)

    personal_form = PersonalInfoForm(instance=user)
    contact_form = ContactInfoForm(instance=user)
    image_form = ProfileImageForm(instance=user)
    password_form = CustomPasswordChangeForm(user=user)
    student_form = StudentProfileForm(instance=student_profile) if student_profile else None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'personal_info':
            personal_form = PersonalInfoForm(request.POST, instance=user)
            if personal_form.is_valid():
                personal_form.save()
                return _success_response(request, _("Personal information updated successfully."))
            else:
                return _form_error_response(request, personal_form)

        elif form_type == 'contact_info':
            contact_form = ContactInfoForm(request.POST, instance=user)
            if contact_form.is_valid():
                contact_form.save()
                return _success_response(request, _("Contact information updated successfully."))
            else:
                return _form_error_response(request, contact_form)

        elif form_type == 'profile_image':
            image_form = ProfileImageForm(request.POST, request.FILES, instance=user)
            if image_form.is_valid():
                image_form.save()
                return _success_response(request, _("Profile image updated successfully."))
            else:
                return _form_error_response(request, image_form)

        elif form_type == 'password_change':
            password_form = CustomPasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user) # Keep user logged in
                return _success_response(request, _("Password changed successfully."))
            else:
                return _form_error_response(request, password_form)

        elif form_type == 'student_profile' and student_form:
            student_form = StudentProfileForm(request.POST, instance=student_profile)
            if student_form.is_valid():
                student_form.save()
                return _success_response(request, _("Student profile updated successfully."))
            else:
                return _form_error_response(request, student_form)

    context = {
        'user': user,
        'personal_form': personal_form,
        'contact_form': contact_form,
        'image_form': image_form,
        'password_form': password_form,
        'student_form': student_form,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('dashboard/fragments/profile.html', context, request=request)
        return JsonResponse({'form_html': html})

    return render(request, 'dashboard/fragments/profile.html', context)

def _success_response(request, message):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': str(message)})
    messages.success(request, message)
    return redirect('profile_view')

def _form_error_response(request, form):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        errors = []
        for field, error_list in form.errors.items():
            for error in error_list:
                errors.append(f"{field.replace('_', ' ').title()}: {error}")
        return JsonResponse({'success': False, 'errors': errors})

    # Fallback for non-AJAX
    for field, error_list in form.errors.items():
        for error in error_list:
            messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    return redirect('profile_view')
