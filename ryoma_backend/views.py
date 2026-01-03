import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def ask_ryoma(request):
    """
    ダミー回答API:
      POST /api/ask_ryoma
      body: {"question": "..."}
      resp: {"answer": "..."}
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "question is required"}, status=400)

    # ここは次ステップで Bedrock + pgvector に置き換えるでごわす
    answer = f"（ダミー回答でごわす）質問『{question}』を受け取ったぜよ。"

    return JsonResponse({
        "answer": answer,
        "debug": {
            "received_question": question
        }
    }, json_dumps_params={"ensure_ascii": False})
