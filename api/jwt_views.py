"""
JWT-Protected API views for ApplyBaMa dashboard.

These views demonstrate how to use the @jwt_required decorator
to protect API endpoints with JWT authentication.
"""

import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from core.utils.jwt_auth import JWTManager
from core.middleware.jwt_auth import jwt_required, optional_jwt_auth
from django.utils.translation import gettext_lazy as _


@csrf_exempt
@require_GET
def user_profile_api(request):
    """
    Get current user's profile information.

    Requires JWT authentication.
    Returns user data based on the authenticated token.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return JsonResponse({
            'error': _('Authentication required'),
            'detail': _('Please provide a valid JWT token.')
        }, status=401)

    user = request.user

    user_data = {
        'id': user.id,
        'email': user.email,
        'username': user.username,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'full_name': user.get_full_name() or user.username,
        'user_type': user.user_type,
        'gender': user.gender or '',
        'date_of_birth': str(user.date_of_birth) if user.date_of_birth else None,
        'mobile': user.mobile or '',
        'country': {
            'id': user.country.id if user.country else None,
            'name': user.country.name if user.country else None,
        } if user.country else None,
        'city': {
            'id': user.city.id if user.city else None,
            'name': user.city.name if user.city else None,
        } if user.city else None,
        'profile_image': user.profile_image.url if user.profile_image else None,
        'is_representative': user.is_representative,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
    }

    return JsonResponse({
        'success': True,
        'user': user_data
    })


@csrf_exempt
@require_POST
def update_profile_api(request):
    """
    Update current user's profile.

    Requires JWT authentication.
    Accepts JSON body with profile fields to update.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return JsonResponse({
            'error': _('Authentication required')
        }, status=401)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({
            'error': _('Invalid JSON payload')
        }, status=400)

    user = request.user
    updated_fields = []

    # Allowed fields for update
    allowed_fields = [
        'first_name', 'last_name', 'gender', 'date_of_birth',
        'mobile', 'country', 'city'
    ]

    # Handle country/city as IDs
    country_id = data.get('country')
    city_id = data.get('city')

    from core.models import Country, City

    if country_id:
        try:
            country = Country.objects.get(id=country_id)
            user.country = country
            updated_fields.append('country')
        except Country.DoesNotExist:
            return JsonResponse({
                'error': _('Invalid country ID')
            }, status=400)

    if city_id:
        try:
            city = City.objects.get(id=city_id)
            user.city = city
            updated_fields.append('city')
        except City.DoesNotExist:
            return JsonResponse({
                'error': _('Invalid city ID')
            }, status=400)

    # Update simple fields
    for field in allowed_fields:
        if field in ('country', 'city'):
            continue  # Already handled above
        if field in data and field != 'date_of_birth':
            setattr(user, field, data[field])
            updated_fields.append(field)

    # Handle date_of_birth
    if 'date_of_birth' in data and data['date_of_birth']:
        try:
            from datetime import datetime
            user.date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
            updated_fields.append('date_of_birth')
        except (ValueError, TypeError):
            return JsonResponse({
                'error': _('Invalid date format. Use YYYY-MM-DD.')
            }, status=400)

    # Save user
    user.save()

    return JsonResponse({
        'success': True,
        'message': _('Profile updated successfully.'),
        'updated_fields': updated_fields
    })


@csrf_exempt
@require_GET
def dashboard_stats_api(request):
    """
    Get dashboard statistics for the authenticated user.

    Returns different data based on user type:
    - Default (student): Applications, notifications count
    - Agent: Managed students count, applications handled
    - Company: Company profile data
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return JsonResponse({
            'error': _('Authentication required')
        }, status=401)

    user = request.user
    from core.models import Application, Notification

    stats = {
        'user_type': user.user_type
    }

    if user.user_type == 'default':
        # Student stats
        stats['applications_count'] = Application.objects.filter(
            student=user
        ).count()

        stats['notifications_unread'] = NotificationRecipient.objects.filter(
            user=user,
            is_read=False
        ).count()

        stats['completed_applications'] = Application.objects.filter(
            student=user,
            status='finished'
        ).count()

        stats['in_progress_applications'] = Application.objects.filter(
            student=user,
            status='in_progress'
        ).count()

    elif user.user_type == 'agent':
        # Agent stats
        from core.models import AgentProfile

        try:
            agent_profile = AgentProfile.objects.get(user=user)
            stats['managed_students_count'] = Application.objects.filter(
                agent=user
            ).values('student').distinct().count()

            stats['total_applications'] = Application.objects.filter(
                agent=user
            ).count()
        except AgentProfile.DoesNotExist:
            stats['managed_students_count'] = 0
            stats['total_applications'] = 0

    elif user.user_type == 'company':
        # Company stats
        from core.models import CompanyProfile

        try:
            company_profile = CompanyProfile.objects.get(user=user)
            stats['agents_count'] = company_profile.agents.count()
        except CompanyProfile.DoesNotExist:
            stats['agents_count'] = 0

    return JsonResponse({
        'success': True,
        'stats': stats
    })


@csrf_exempt
@require_GET
def my_applications_api(request):
    """
    Get authenticated user's applications.

    Supports pagination via query parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 10, max: 100)
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return JsonResponse({
            'error': _('Authentication required')
        }, status=401)

    user = request.user
    from core.models import Application

    # Parse pagination params
    try:
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 10)), 100)
    except ValueError:
        return JsonResponse({
            'error': _('Invalid pagination parameters')
        }, status=400)

    # Get applications based on user type
    if user.user_type == 'default':
        queryset = Application.objects.filter(student=user)
    elif user.user_type == 'agent':
        queryset = Application.objects.filter(agent=user)
    else:
        queryset = Application.objects.none()

    # Order by created_at descending
    queryset = queryset.order_by('-created_at')

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    applications = queryset[start:end]

    # Serialize applications
    apps_data = []
    for app in applications:
        apps_data.append({
            'id': app.id,
            'application_name': app.application_name,
            'status': app.status,
            'step': app.step,
            'student': {
                'id': app.student.id,
                'username': app.student.username,
                'full_name': app.student.get_full_name() or app.student.username,
            },
            'program': {
                'id': app.program.id if app.program else None,
                'name': app.program.name if app.program else None,
                'university': app.program.university.name if app.program and app.program.university else None,
            } if app.program else None,
            'created_at': app.created_at.isoformat() if app.created_at else None,
            'updated_at': app.updated_at.isoformat() if app.updated_at else None,
        })

    total_count = queryset.count()
    total_pages = (total_count + page_size - 1) // page_size

    return JsonResponse({
        'success': True,
        'applications': apps_data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1
        }
    })


@csrf_exempt
@require_GET
def notifications_list_api(request):
    """
    Get notifications for the authenticated user.

    Query parameters:
    - unread_only: Filter to unread notifications only (true/false)
    - limit: Maximum notifications to return (default: 20)
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return JsonResponse({
            'error': _('Authentication required')
        }, status=401)

    user = request.user
    from core.models import NotificationRecipient

    # Parse parameters
    unread_only = request.GET.get('unread_only', '').lower() == 'true'
    try:
        limit = min(int(request.GET.get('limit', 20)), 100)
    except ValueError:
        limit = 20

    # Build queryset
    queryset = NotificationRecipient.objects.filter(
        user=user
    ).select_related('notification', 'notification__sender')

    if unread_only:
        queryset = queryset.filter(is_read=False)

    # Order and limit
    notifications = queryset.order_by('-notification__created_at')[:limit]

    # Serialize
    notifs_data = []
    for nr in notifications:
        notifs_data.append({
            'id': nr.notification.id,
            'title': nr.notification.title,
            'message': nr.notification.message,
            'notification_type': nr.notification.notification_type,
            'is_read': nr.is_read,
            'sender': {
                'id': nr.notification.sender.id if nr.notification.sender else None,
                'username': nr.notification.sender.username if nr.notification.sender else None,
            },
            'created_at': nr.notification.created_at.isoformat() if nr.notification.created_at else None,
            'read_at': nr.read_at.isoformat() if nr.read_at else None,
        })

    # Unread count
    unread_count = NotificationRecipient.objects.filter(
        user=user,
        is_read=False
    ).count()

    return JsonResponse({
        'success': True,
        'notifications': notifs_data,
        'unread_count': unread_count
    })


# Helper import at the bottom to avoid circular imports
from core.models import NotificationRecipient