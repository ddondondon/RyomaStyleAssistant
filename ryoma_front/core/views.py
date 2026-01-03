import os
import json
import random
import subprocess

import psycopg2
import boto3

from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.csrf import csrf_exempt


CHUNKS_S3_URI = os.getenv("CHUNKS_S3_URI", "s3://ryoma-style-assistant/corpus/chunks/chunks.jsonl")
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "400"))


def home(request):
    tpl = loader.get_template("home.html")
    return HttpResponse(tpl.render({"title": "Ryoma RAG (Preview)"}, request))


def health(request):
    return JsonResponse({"status": "ok"})


def _pg_conn():
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return psycopg2.connect(dsn)

    host = os.getenv("PGHOST")
    port = os.getenv("PGPORT", "5432")
    dbname = os.getenv("PGDATABASE")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")
    sslmode = os.getenv("PGSSLMODE")

    if not all([host, dbname, user, password]):
        raise RuntimeError(
            "Postgres env vars missing. Need PGHOST/PGDATABASE/PGUSER/PGPASSWORD or DATABASE_URL"
        )

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        sslmode=sslmode,
    )


def _dummy_embedding_1024(text: str) -> list[float]:
    seed = abs(hash(text)) % (2**32)
    rnd = random.Random(seed)
    return [rnd.uniform(-1.0, 1.0) for _ in range(1024)]


def _pgvector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _fetch_chunk_text_from_s3(chunk_id: str) -> str | None:
    """
    最小実装：aws cli + grep で1件引くでごわす（top_kが小さい前提）
    本番ではローカルキャッシュ等に置き換える想定でごわす。
    """
    pattern = f'"chunk_id": "{chunk_id}"'

    cmd = [
        "sh",
        "-lc",
        f'aws s3 cp "{CHUNKS_S3_URI}" - | grep -m 1 {json.dumps(pattern)}',
    ]

    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

    line = out.decode("utf-8", errors="replace").strip()
    if not line:
        return None

    try:
        obj = json.loads(line)
    except Exception:
        return None

    text = obj.get("text")
    if not isinstance(text, str):
        return None

    return text[:MAX_TEXT_CHARS]


def _extract_nova_text(out: dict) -> str:
    """
    Nova系レスポンスからテキストを安全に取り出すでごわす。
    期待フォーマット:
      {"output":{"message":{"content":[{"text":"..."}],"role":"assistant"}}, ...}
    """
    try:
        msg = (out.get("output") or {}).get("message") or {}
        content = msg.get("content") or []
        if isinstance(content, list) and content:
            first = content[0] or {}
            t = first.get("text") or ""
            return " ".join(str(t).split())
    except Exception:
        pass
    return ""


def _make_answer_fallback(matches: list[dict]) -> str:
    """
    フォールバック：先頭チャンク本文を返すでごわす。
    """
    if not matches:
        return "該当する情報が見つからなかったでごわす。"
    t = " ".join(str(matches[0].get("text") or "").split())
    return t or "チャンク本文が取得できなかったでごわす。"


def _make_answer_llm(question: str, matches: list[dict]) -> str:
    """
    最低限のRAG回答（LLMあり）でごわす。
    - matches のテキストを根拠としてプロンプトに入れる
    - Bedrock(Nova Micro) を inference profile ARN で呼ぶ
    - Novaは role=system を受け付けないことがあるため、指示は user に同梱するでごわす
    """
    profile_arn = os.getenv("BEDROCK_LLM_PROFILE_ARN", "").strip()
    if not profile_arn:
        raise RuntimeError("BEDROCK_LLM_PROFILE_ARN is not set")

    ctx_parts = []
    for i, m in enumerate(matches[:3], start=1):
        t = " ".join(str(m.get("text") or "").split())
        if not t:
            continue
        t = t[:800]
        ctx_parts.append(f"[{i}] {t}")
    context = "\n".join(ctx_parts) if ctx_parts else "(根拠テキストなし)"

    # system相当の指示を user メッセージへ統合
    prompt = f"""あなたは坂本龍馬に関するRAGアシスタントでごわす。
次の「根拠テキスト」だけを使って、日本語で簡潔に答えるでごわす。
根拠に無いことは推測せず「不明でごわす」と言うでごわす。
回答は2〜4文で簡潔にするでごわす。

質問:
{question}

根拠テキスト:
{context}
"""

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-northeast-1"
    brt = boto3.client("bedrock-runtime", region_name=region)

    body = {
        "messages": [
            {"role": "user", "content": [{"text": prompt}]},
        ],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0.2},
    }

    resp = brt.invoke_model(
        modelId=profile_arn,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    )
    out = json.loads(resp["body"].read())

    text = _extract_nova_text(out)
    if not text:
        raise RuntimeError(f"empty llm text (keys={list(out.keys())})")
    return text


@csrf_exempt
def ask_ryoma(request):
    """
    最低限のRAG（検索 + 根拠取得 + LLM回答）でごわす。
    - Titan embed v2 で質問embedding
    - pgvector で top_k 検索
    - S3 chunks.jsonl から text を補完
    - Nova Micro（inference profile ARN）で answer を生成
    - どこかが死んでも落とさずフォールバックで返す
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        payload = json.loads((request.body or b"").decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    question = (payload.get("question") or "").strip()
    force_dummy = bool(payload.get("force_dummy"))
    force_no_llm = bool(payload.get("force_no_llm"))  # デバッグ用：LLM無効化

    if not question:
        return JsonResponse({"error": "question is required"}, status=400)

    top_k = int(payload.get("top_k") or 5)
    top_k = max(1, min(top_k, 10))

    try:
        # 1) embedding
        bedrock_error = None
        if force_dummy:
            q_vec = _dummy_embedding_1024(question)
            mode = "dummy_embedding_forced"
        else:
            try:
                q_vec = _bedrock_embedding_1024(question)
                mode = "bedrock_embedding"
            except Exception as e:
                q_vec = _dummy_embedding_1024(question)
                mode = "dummy_embedding_fallback"
                bedrock_error = str(e)

        q_vec_lit = _pgvector_literal(q_vec)

        # 2) pgvector search
        sql = """
        SELECT
            id,
            doc_id,
            chunk_id,
            chunk_index,
            title,
            source,
            lang,
            origin_s3_uri,
            1 - (embedding <=> %s::vector) AS cosine_similarity
        FROM rag_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """

        matches = []
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (q_vec_lit, q_vec_lit, top_k))
                for row in cur.fetchall():
                    (
                        rid,
                        doc_id,
                        chunk_id,
                        chunk_index,
                        title,
                        source,
                        lang,
                        origin_s3_uri,
                        cos,
                    ) = row

                    text = _fetch_chunk_text_from_s3(chunk_id)

                    matches.append(
                        {
                            "id": rid,
                            "doc_id": doc_id,
                            "chunk_id": chunk_id,
                            "chunk_index": chunk_index,
                            "title": title,
                            "source": source,
                            "lang": lang,
                            "origin_s3_uri": origin_s3_uri,
                            "cosine_similarity": float(cos) if cos is not None else None,
                            "text": text,
                        }
                    )

        # 3) answer generation (LLM -> fallback)
        answer_error = None
        if force_no_llm:
            answer = _make_answer_fallback(matches)
            answer_error = "force_no_llm=true"
        else:
            try:
                answer = _make_answer_llm(question, matches)
            except Exception as e:
                answer_error = str(e)
                answer = _make_answer_fallback(matches)

        return JsonResponse(
            {
                "mode": f"{mode}+s3_text",
                "question": question,
                "build_id": "debug-REFLECT-OK",
                "top_k": top_k,
                "chunks_s3_uri": CHUNKS_S3_URI,
                "matches": matches,
                "bedrock_error": bedrock_error,
                "answer_error": answer_error,
                "answer": answer,
            },
            json_dumps_params={"ensure_ascii": False},
        )

    except Exception as e:
        return JsonResponse(
            {"error": str(e)},
            status=500,
            json_dumps_params={"ensure_ascii": False},
        )


def _bedrock_embedding_1024(text: str) -> list[float]:
    """
    Bedrock(Titan Embed v2)で1024次元embeddingを返すでごわす
    """
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-northeast-1"
    model_id = os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")

    brt = boto3.client("bedrock-runtime", region_name=region)

    body = {"inputText": text}
    dims = os.getenv("BEDROCK_EMBED_DIMS")
    norm = os.getenv("BEDROCK_EMBED_NORMALIZE")
    if dims:
        try:
            body["dimensions"] = int(dims)
        except Exception:
            pass
    if norm is not None:
        body["normalize"] = norm.lower() in ("1", "true", "yes", "on")

    resp = brt.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    )

    payload = json.loads(resp["body"].read())
    emb = payload.get("embedding")
    if not emb or len(emb) != 1024:
        raise RuntimeError(f"unexpected embedding response: keys={list(payload.keys())}")
    return emb

