# realtime/routing.py
from django.urls import re_path

from . import consumers

# Single source of truth for the socket path: the context processor publishes
# it to the browser ("/" + WS_NOTIFY_PATH) and the regex below serves it, so
# the two can never drift apart.
WS_NOTIFY_PATH = "ws/notify/"

websocket_urlpatterns = [
    re_path(r"^" + WS_NOTIFY_PATH + "$", consumers.NotifyConsumer.as_asgi()),
]
