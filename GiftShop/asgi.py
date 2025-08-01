"""
ASGI config for GiftShop project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.sessions import SessionMiddlewareStack
import store.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GiftShop.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": SessionMiddlewareStack(
        AuthMiddlewareStack(
            URLRouter(
                store.routing.websocket_urlpatterns
            )
        )
    ),
})
