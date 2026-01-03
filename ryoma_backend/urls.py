from django.urls import path
from .views import ask_ryoma

urlpatterns = [
    path("api/ask_ryoma", ask_ryoma),
]

