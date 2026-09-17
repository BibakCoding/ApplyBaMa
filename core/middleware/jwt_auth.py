"""
JWT Authentication Middleware for ApplyBaMa.

This middleware allows JWT token authentication for API requests
while preserving the existing session-based authentication.
"""

import jwt
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse

from core.utils.jwt_auth import JWTManager

User = get_user_model()


class JWTAuthenticationMiddleware:
    """
    Middleware that authenticates users using JWT tokens in the Authorization header.

    This middleware checks for a JWT token in the Authorization header and
    authenticates the user if the token is valid. It preserves the existing
    session-based authentication for non-API requests.

    Usage:
    - Add 'core.middleware.jwt_auth.JWTAuthenticationMiddleware' to MIDDLEWARE
    - Position after 'django.contrib.auth.middleware.AuthenticationMiddleware'
    - Client should send: Authorization: Bearer <jwt_token>
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only attempt JWT authentication for API requests or when Authorization header is present
        if self._should_attempt_jwt_auth(request):
            self._authenticate_with_jwt(request)

        response = self.get_response(request)
        return response

    def _should_attempt_jwt_auth(self, request):
        """
        Determine if JWT authentication should be attempted.

        Returns True if:
        - Request path starts with /api/
        - Authorization header is present
        - User is not already authenticated
        """
        # Don't override existing authenticated user
        if hasattr(request, 'user') and request.user.is_authenticated:
            return False

        # Check for Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header:
            return False

        # Only process Bearer tokens
        return auth_header.startswith('Bearer ')

    def _authenticate_with_jwt(self, request):
        """
        Authenticate the request using JWT token from Authorization header.

        Sets request.user if authentication is successful.
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header:
            return

        # Extract token from "Bearer <token>"
        parts = auth_header.split(' ', 1)
        if len(parts) != 2:
            return

        token = parts[1].strip()

        if not token:
            return

        try:
            # Verify and get user from token
            user = JWTManager.get_user_from_token(token)

            if user and user.is_active:
                # Set user on request
                request.user = user

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
            # Token is invalid or expired - don't set user
            pass


def jwt_required(view_func):
    """
    Decorator that requires JWT authentication for a view.

    Usage:
        @jwt_required
        def my_api_view(request):
            # request.user is guaranteed to be authenticated
            pass

    Returns 401 Unauthorized if no valid JWT token is provided.
    """
    def wrapper(request, *args, **kwargs):
        # Check if user is authenticated via JWT
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            # Try to authenticate with JWT
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')

            if not auth_header or not auth_header.startswith('Bearer '):
                return JsonResponse({
                    'error': _('Authentication required'),
                    'detail': _('Please provide a valid JWT token in the Authorization header.')
                }, status=401)

            parts = auth_header.split(' ', 1)
            if len(parts) != 2:
                return JsonResponse({
                    'error': _('Invalid authorization header format')
                }, status=401)

            token = parts[1].strip()

            try:
                user = JWTManager.get_user_from_token(token)

                if not user or not user.is_active:
                    return JsonResponse({
                        'error': _('Invalid or expired token')
                    }, status=401)

                request.user = user

            except jwt.ExpiredSignatureError:
                return JsonResponse({
                    'error': _('Token has expired'),
                    'detail': _('Please refresh your token or login again.')
                }, status=401)
            except jwt.InvalidTokenError:
                return JsonResponse({
                    'error': _('Invalid token')
                }, status=401)
            except Exception as e:
                return JsonResponse({
                    'error': _('Authentication failed'),
                    'detail': str(e)
                }, status=401)

        return view_func(request, *args, **kwargs)

    return wrapper


def optional_jwt_auth(view_func):
    """
    Decorator that optionally authenticates with JWT if token is provided.

    Unlike @jwt_required, this doesn't require authentication but will
    set request.user if a valid token is provided.

    Usage:
        @optional_jwt_auth
        def my_view(request):
            if request.user.is_authenticated:
                # User is authenticated via JWT
                pass
            else:
                # No JWT token provided
                pass
    """
    def wrapper(request, *args, **kwargs):
        # Check if user is already authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        # Try to authenticate with JWT
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if auth_header and auth_header.startswith('Bearer '):
            parts = auth_header.split(' ', 1)
            if len(parts) == 2:
                token = parts[1].strip()
                try:
                    user = JWTManager.get_user_from_token(token)
                    if user and user.is_active:
                        request.user = user
                except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
                    pass

        return view_func(request, *args, **kwargs)

    return wrapper