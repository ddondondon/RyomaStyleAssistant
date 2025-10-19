# api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("version", views.version, name="version"),
    path("ask", views.ask_stub, name="ask_stub"),  # 後でBedrock連携に差し替え
]
