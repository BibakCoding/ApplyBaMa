"""
JWT Configuration for ApplyBaMa.

This module provides JWT settings that can be imported into base.py
settings to maintain compatibility with existing authentication.
"""

# JWT Secret Key (use Django's SECRET_KEY as fallback)
# NOTE: The actual value is resolved in JWTManager class using getattr with 'or' fallback
JWT_SECRET_KEY = None  # Will be resolved at runtime to settings.SECRET_KEY

# Token expiration times (in hours)
JWT_ACCESS_TOKEN_LIFETIME = 24  # 24 hours
JWT_REFRESH_TOKEN_LIFETIME = 7 * 24  # 7 days (168 hours)

# JWT algorithm
JWT_ALGORITHM = 'HS256'

# Token type claim
JWT_TOKEN_TYPE_CLAIM = 'token_type'

# User ID claim
JWT_USER_ID_CLAIM = 'user_id'

# Settings for middleware
JWT_AUTH_HEADER_PREFIX = 'Bearer'

# Enable/disable JWT authentication for API
JWT_AUTH_ENABLED = True

# Paths that require JWT authentication (regex patterns)
JWT_PROTECTED_PATHS = [
    r'^/api/.*$',  # All API endpoints
]

# Paths that are exempt from JWT authentication
JWT_AUTH_EXEMPT_PATHS = [
    r'^/api/token/$',          # Token obtain
    r'^/api/token/refresh/$',  # Token refresh
    r'^/api/token/verify/$',   # Token verify
    r'^/api/register/$',       # Registration
    r'^/api/cities/$',         # Public cities API
]

# Middleware configuration
JWT_AUTH_MIDDLEWARE = 'core.middleware.jwt_auth.JWTAuthenticationMiddleware'

# Custom payload handler
def jwt_payload_handler(user):
    """
    Custom JWT payload handler.

    Args:
        user: Django User instance

    Returns:
        dict: Custom payload for JWT token
    """
    from datetime import datetime

    return {
        'user_id': user.id,
        'email': user.email,
        'username': user.username,
        'user_type': user.user_type,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'is_active': user.is_active,
        'created_at': user.date_joined.isoformat() if user.date_joined else '',
    }

# Custom response handler
def jwt_response_handler(data, user=None, request=None):
    """
    Custom JWT response handler.

    Args:
        data: Dictionary containing access and refresh tokens
        user: Authenticated user (optional)
        request: HTTP request (optional)

    Returns:
        dict: Custom response payload
    """
    response_data = {
        'access': data.get('access'),
        'refresh': data.get('refresh'),
        'expires_in': 86400,  # 24 hours in seconds
        'token_type': 'Bearer',
    }

    if user:
        response_data['user'] = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'user_type': user.user_type,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
        }

    return response_data