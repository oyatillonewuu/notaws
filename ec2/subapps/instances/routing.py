from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/instances/<int:pk>/terminal/", consumers.TerminalConsumer.as_asgi()),
]
