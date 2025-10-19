# api/views.py
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

@require_GET
def health(request):
    return JsonResponse({"status": "ok", "ts": datetime.now().isoformat()})

@require_GET
def version(request):
    return JsonResponse({"app": "RyomaStyleAssistant", "backend": "django", "version": "0.1.0"})

@require_POST
def ask_stub(request):
    # TODO: Week5でBedrock(LangChainでも可)を噛ませる
    # 期待入力: {"question": "..."}
    return JsonResponse({"answer": "(stub) ここにBedrockの回答が入るでごわす", "sources": []})
