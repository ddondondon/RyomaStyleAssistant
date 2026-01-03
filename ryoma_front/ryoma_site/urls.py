from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve

from core.views import home, health, ask_ryoma

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("health/", health, name="health"),

    # API
    path("api/ask_ryoma", ask_ryoma, name="ask_ryoma"),

    # assets
    re_path(r"^assets/(?P<path>.*)$", serve, {"document_root": "/app/assets"}),
]
