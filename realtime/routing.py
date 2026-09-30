# realtime/routing.py
from django.urls import re_path

from . import chat, consumers

# Single source of truth for the socket paths: the context processor publishes
# them to the browser ("/" + WS_*_PATH) and the regexes below serve them, so
# the two can never drift apart.
WS_NOTIFY_PATH = "ws/notify/"
WS_CHAT_PATH = chat.CHAT_WS_PATH

websocket_urlpatterns = [
    re_path(r"^" + WS_NOTIFY_PATH + "$", consumers.NotifyConsumer.as_asgi()),
    re_path(r"^" + WS_CHAT_PATH + "$", chat.ChatConsumer.as_asgi()),
]
