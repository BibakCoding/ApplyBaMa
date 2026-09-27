"""
ASGI config for ApplyBaMa project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ApplyBaMa.settings')

# Import the ASGI application before any consumer, so Django's app registry is
# populated before models are touched by imports (Channels' standard pattern).
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        # Plain HTTP requests keep going through Django exactly as before.
        "http": django_asgi_app,
        # WebSockets: validate the Origin header against ALLOWED_HOSTS (same
        # protection cross-site pages get on HTTP), then run the standard auth
        # middleware so consumers see request.user from the session cookie.
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
