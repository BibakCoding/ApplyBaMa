"""
JWT authentication utilities for ApplyBaMa.

This module provides JWT token generation, verification, and user authentication
for both session-based and token-based authentication flows.
"""

import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

User = get_user_model()


class JWTManager:
    """
    Manage JWT token generation, verification, and user authentication.

    JWT tokens contain:
    - user_id: The user's primary key
    - email: User's email for identification
    - user_type: User type (default/company/agent)
    - exp: Expiration timestamp
    - iat: Issued at timestamp
    """

    # Secret key from Django settings, fallback to SECRET_KEY
    SECRET_KEY = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)

    # Token expiration times (in hours)
    ACCESS_TOKEN_LIFETIME = getattr(settings, 'JWT_ACCESS_TOKEN_LIFETIME', 24)  # 24 hours
    REFRESH_TOKEN_LIFETIME = getattr(settings, 'JWT_REFRESH_TOKEN_LIFETIME', 7 * 24)  # 7 days

    # JWT algorithm
    ALGORITHM = 'HS256'

    @classmethod
    def create_access_token(cls, user):
        """
        Create an access token for the given user.

        Args:
            user: Django User instance

        Returns:
            str: JWT access token
        """
        payload = {
            'user_id': user.id,
            'email': user.email,
            'user_type': user.user_type,
            'exp': datetime.utcnow() + timedelta(hours=cls.ACCESS_TOKEN_LIFETIME),
            'iat': datetime.utcnow(),
            'token_type': 'access',
        }

        # Add username if available
        if user.username:
            payload['username'] = user.username

        return jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    def create_refresh_token(cls, user):
        """
        Create a refresh token for the given user.

        Args:
            user: Django User instance

        Returns:
            str: JWT refresh token
        """
        payload = {
            'user_id': user.id,
            'email': user.email,
            'user_type': user.user_type,
            'exp': datetime.utcnow() + timedelta(hours=cls.REFRESH_TOKEN_LIFETIME),
            'iat': datetime.utcnow(),
            'token_type': 'refresh',
        }

        return jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    def verify_token(cls, token, token_type='access'):
        """
        Verify a JWT token and return the decoded payload.

        Args:
            token (str): JWT token to verify
            token_type (str): Expected token type ('access' or 'refresh')

        Returns:
            dict: Decoded token payload

        Raises:
            jwt.ExpiredSignatureError: Token has expired
            jwt.InvalidTokenError: Token is invalid
            ValidationError: Token type mismatch
        """
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])

            # Verify token type
            if payload.get('token_type') != token_type:
                raise ValidationError(_(f'Invalid token type. Expected {token_type}.'))

            return payload

        except jwt.ExpiredSignatureError:
            raise jwt.ExpiredSignatureError(_('Token has expired'))
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(_('Invalid token'))

    @classmethod
    def get_user_from_token(cls, token, token_type='access'):
        """
        Get user from JWT token.

        Args:
            token (str): JWT token
            token_type (str): Expected token type

        Returns:
            User: Django User instance or None if not found

        Raises:
            jwt.ExpiredSignatureError: Token has expired
            jwt.InvalidTokenError: Token is invalid
        """
        try:
            payload = cls.verify_token(token, token_type)
            user_id = payload.get('user_id')

            if not user_id:
                return None

            try:
                return User.objects.get(id=user_id, is_active=True)
            except User.DoesNotExist:
                return None

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValidationError):
            return None

    @classmethod
    def refresh_access_token(cls, refresh_token):
        """
        Create a new access token using a valid refresh token.

        Args:
            refresh_token (str): Valid refresh token

        Returns:
            str: New access token

        Raises:
            jwt.ExpiredSignatureError: Refresh token has expired
            jwt.InvalidTokenError: Refresh token is invalid
        """
        user = cls.get_user_from_token(refresh_token, token_type='refresh')

        if not user:
            raise jwt.InvalidTokenError(_('Invalid refresh token'))

        return cls.create_access_token(user)


def authenticate_with_jwt(token):
    """
    Authenticate user using JWT token.

    Args:
        token (str): JWT access token

    Returns:
        tuple: (user, None) if authenticated, (None, None) otherwise
    """
    user = JWTManager.get_user_from_token(token)
    return (user, None) if user else (None, None)


def get_user_jwt_payload(user):
    """
    Get JWT payload structure for a user.

    Args:
        user: Django User instance

    Returns:
        dict: User payload for JWT tokens
    """
    return {
        'user_id': user.id,
        'email': user.email,
        'user_type': user.user_type,
        'username': user.username,
    }