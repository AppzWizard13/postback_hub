# routing.py
from django.urls import path
from .consumers import  OrderConsumer
from django.urls import path
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

ws_urlpatterns = [
    path('ws/order_updates/<str:last_keyword>/', OrderUpdateConsumer.as_asgi()),
    
]

application = ProtocolTypeRouter(
    {
        "websocket": AuthMiddlewareStack(
            URLRouter(ws_urlpatterns)
        ),
    }
)
