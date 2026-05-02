import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notaws.settings")

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from ec2.subapps.instances.routing import websocket_urlpatterns

# AllowedHostsOriginValidator blocks cross-site WebSocket hijacking — without
# it, any page could open a WS to our terminal using the user's session cookie.
# Reads ALLOWED_HOSTS from settings.
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
