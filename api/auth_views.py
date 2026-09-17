"""
JWT authentication API views for ApplyBaMa.

Provides endpoints for obtaining and refreshing JWT tokens while maintaining
compatibility with the existing session-based authentication system.
"""

import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from core.utils.jwt_auth import JWTManager
from authentication.forms import LoginForm, RegisterForm

User = get_user_model()


@csrf_exempt
@require_POST
def obtain_token(request):
    """
    Obtain JWT access and refresh tokens by providing credentials.

    Expected JSON payload:
    {
        "username": "email_or_username",
        "password": "password"
    }

    Returns:
    {
        "access": "jwt_access_token",
        "refresh": "jwt_refresh_token",
        "user": {
            "id": user_id,
            "email": user_email,
            "username": username,
            "user_type": user_type
        }
    }
    """
    try:
        # Parse JSON payload
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({
                'error': _('Invalid JSON payload')
            }, status=400)

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return JsonResponse({
                'error': _('Username and password are required')
            }, status=400)

        # Use existing LoginForm for validation
        form = LoginForm(data={'username': username, 'password': password})

        if not form.is_valid():
            errors = form.errors.get_json_data()
            return JsonResponse({
                'error': _('Authentication failed'),
                'errors': errors
            }, status=401)

        # Get authenticated user from form
        user = form.user

        # Generate tokens
        access_token = JWTManager.create_access_token(user)
        refresh_token = JWTManager.create_refresh_token(user)

        return JsonResponse({
            'access': access_token,
            'refresh': refresh_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'user_type': user.user_type,
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
            }
        })

    except Exception as e:
        return JsonResponse({
            'error': _('Authentication failed'),
            'detail': str(e)
        }, status=500)


@csrf_exempt
@require_POST
def refresh_token(request):
    """
    Refresh an access token using a valid refresh token.

    Expected JSON payload:
    {
        "refresh": "jwt_refresh_token"
    }

    Returns:
    {
        "access": "new_jwt_access_token",
        "user": {
            "id": user_id,
            "email": user_email,
            "username": username,
            "user_type": user_type
        }
    }
    """
    try:
        # Parse JSON payload
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({
                'error': _('Invalid JSON payload')
            }, status=400)

        refresh_token = data.get('refresh')

        if not refresh_token:
            return JsonResponse({
                'error': _('Refresh token is required')
            }, status=400)

        # Verify refresh token and get user
        user = JWTManager.get_user_from_token(refresh_token, token_type='refresh')

        if not user:
            return JsonResponse({
                'error': _('Invalid or expired refresh token')
            }, status=401)

        # Generate new access token
        access_token = JWTManager.create_access_token(user)

        return JsonResponse({
            'access': access_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'user_type': user.user_type,
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
            }
        })

    except Exception as e:
        return JsonResponse({
            'error': _('Token refresh failed'),
            'detail': str(e)
        }, status=500)


@csrf_exempt
@require_POST
def verify_token(request):
    """
    Verify if a token is valid and return user information.

    Expected JSON payload:
    {
        "token": "jwt_token"
    }

    Returns:
    {
        "valid": true/false,
        "user": {
            "id": user_id,
            "email": user_email,
            "username": username,
            "user_type": user_type
        }  # only if valid
    }
    """
    try:
        # Parse JSON payload
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({
                'error': _('Invalid JSON payload')
            }, status=400)

        token = data.get('token')

        if not token:
            return JsonResponse({
                'error': _('Token is required')
            }, status=400)

        # Verify token and get user
        user = JWTManager.get_user_from_token(token)

        if user:
            return JsonResponse({
                'valid': True,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'user_type': user.user_type,
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                }
            })
        else:
            return JsonResponse({
                'valid': False
            })

    except Exception as e:
        return JsonResponse({
            'valid': False,
            'error': str(e)
        })


@csrf_exempt
@require_POST
def register_user(request):
    """
    Register a new user and return JWT tokens.

    Expected JSON payload:
    {
        "email": "user@example.com",
        "password1": "password",
        "password2": "password"
    }

    Returns:
    {
        "access": "jwt_access_token",
        "refresh": "jwt_refresh_token",
        "user": {
            "id": user_id,
            "email": user_email,
            "username": username,
            "user_type": user_type
        },
        "requires_verification": true/false
    }
    """
    try:
        # Parse JSON payload
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({
                'error': _('Invalid JSON payload')
            }, status=400)

        # Use existing RegisterForm for validation
        form = RegisterForm(data=data)

        if not form.is_valid():
            errors = form.errors.get_json_data()
            return JsonResponse({
                'error': _('Registration failed'),
                'errors': errors
            }, status=400)

        # Get email and password
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password1"]

        # Generate unique username
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Create user (inactive by default, requires email verification)
        user = User.objects.create(
            email=email,
            username=username,
            is_active=False  # Will be activated after email verification
        )
        user.set_password(password)
        user.save()

        # Note: Email verification should be sent via existing authentication flow
        # The existing authentication.views.register_view handles this

        # Generate tokens (user will still need to verify email)
        access_token = JWTManager.create_access_token(user)
        refresh_token = JWTManager.create_refresh_token(user)

        return JsonResponse({
            'access': access_token,
            'refresh': refresh_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'user_type': user.user_type,
            },
            'requires_verification': True,
            'verification_url': f'/auth/confirm_code/{user.pk}/'
        })

    except Exception as e:
        return JsonResponse({
            'error': _('Registration failed'),
            'detail': str(e)
        }, status=500)


@csrf_exempt
@require_POST
def logout_user(request):
    """
    Logout user by invalidating tokens (client-side responsibility).

    Returns:
    {
        "message": "Logged out successfully"
    }
    """
    # Note: JWT tokens are stateless, so invalidation is client-side
    # In a production system, you might want to implement a token blacklist

    return JsonResponse({
        'message': _('Logged out successfully. Please discard your tokens.')
    })