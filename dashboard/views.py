from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from core.forms import ProfileForm
from django.template.loader import render_to_string


@login_required
def dashboard_main(request):
    return render(request, "dashboard/main.html", context={"user": request.user})


@login_required
def dashboard_content(request, page):
    content_map = {
        'welcome': 'dashboard/fragments/welcome.html',
        'announcements': 'dashboard/fragments/announcements.html',
        'profile': 'dashboard/fragments/profile.html',
        'chat': 'dashboard/fragments/chat.html',
        'universities': 'dashboard/fragments/universities.html',
        'programs': 'dashboard/fragments/programs.html',
        'scholarships': 'dashboard/fragments/scholarships.html',
        'new_application': 'dashboard/fragments/new_application.html',
        'my_applications': 'dashboard/fragments/my_applications.html',
        'my_students': 'dashboard/fragments/my_students.html',
    }

    if page not in content_map:
        messages.error(request, _('Page not found.'))
        return redirect('dashboard')

    protected_pages = ['new_application', 'my_applications', 'my_students']
    if page in protected_pages:
        user = request.user
        if not (user.user_type in ['company', 'agent'] or
                (user.user_type == 'student' and user.is_representative)):
            messages.error(request, _('You do not have permission to access this page.'))
            return redirect('dashboard')

    return render(request, content_map[page], context={"user": request.user})


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(
            request.POST,
            request.FILES,
            instance=request.user
        )
        if form.is_valid():
            form.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                # For AJAX requests, return success response
                return JsonResponse({
                    'success': True,
                    'message': _('Profile updated successfully')
                })
            else:
                messages.success(request, _('Profile updated successfully'))
                return redirect('profile_view')
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                # For AJAX requests, return form with errors
                form_html = render_to_string(
                    "dashboard/fragments/profile.html",
                    {'form': form},
                    request=request
                )
                return JsonResponse({
                    'success': False,
                    'form_html': form_html
                })
            else:
                return render(request, "dashboard/fragments/profile.html", {'form': form})

    # GET request
    form = ProfileForm(instance=request.user)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        form_html = render_to_string(
            "dashboard/fragments/profile.html",
            {'form': form},
            request=request
        )
        return JsonResponse({'form_html': form_html})

    return render(request, "dashboard/fragments/profile.html", {'form': form})