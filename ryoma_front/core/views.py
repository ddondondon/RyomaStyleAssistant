from django.http import HttpResponse, JsonResponse
from django.template import loader

def home(request):
    tpl = loader.get_template("home.html")
    return HttpResponse(tpl.render({"title": "Ryoma RAG (Preview)"}, request))

def health(request):
    return JsonResponse({"status":"ok"})

# urls
cat > ryoma_site/urls.py <<'EOF'
from django.contrib import admin
from django.urls import path
from core.views import home, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("health/", health, name="health"),
]
