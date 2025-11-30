#!/usr/bin/env python3
"""
chunks_local.jsonl を読み込み、
Amazon Bedrock Titan Text Embeddings でベクトル化し、
Aurora PostgreSQL（pgvector）に INSERT する最小ループでごわす。

前提:
- チャンクファイル: data/corpus/chunks/chunks_local.jsonl
- Aurora 接続情報: 環境変数 PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
- Bedrock: AWS CLI と同じ認証情報（ロール or 環境変数）で利用可能
"""

import argparse
import json
import os
from pathlib import Path
from typing import Iterator, Dict, Any, List, Optional

import boto3
import psycopg2


def iter_chunks(chunks_path: Path, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
    """
    chunks_local.jsonl を1行ずつ読み込むイテレータでごわす。
    limit が指定されていれば、その件数で打ち切るでごわす。
    """
    count = 0
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            yield record
            count += 1
            if limit is not None and count >= limit:
                break


def get_bedrock_client(region: str):
    """
    Bedrock Runtime クライアントを返すでごわす。
    """
    session = boto3.Session(region_name=region)
    client = session.client("bedrock-runtime")
    return client


def embed_with_titan(
    client,
    text: str,
    model_id: str = "amazon.titan-embed-text-v2:0",
    dimensions: int = 1024,
    normalize: bool = True,
) -> List[float]:
    """
    Titan Text Embeddings で埋め込みベクトルを取得するでごわす。
    v2 を想定して dimensions / normalize も指定しているでごわす。
    """
    body = {
        "inputText": text,
        "dimensions": dimensions,
        "normalize": normalize,
    }
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    response_body = json.loads(response["body"].read())
    embedding = response_body.get("embedding")
    if embedding is None:
        raise RuntimeError("Titan から embedding が返ってこんでごわす。レスポンスを確認してくだされ。")
    return embedding


def get_pg_connection():
    """
    Aurora(PostgreSQL) への接続を返すでごわす。
    必要な環境変数:
      PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
    """
    host = os.environ.get("PGHOST")
    port = os.environ.get("PGPORT", "5432")
    dbname = os.environ.get("PGDATABASE")
    user = os.environ.get("PGUSER")
    password = os.environ.get("PGPASSWORD")

    if not all([host, dbname, user, password]):
        raise RuntimeError(
            "PGHOST, PGDATABASE, PGUSER, PGPASSWORD のいずれかが未設定でごわす。"
        )

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )
    conn.autocommit = True
    return conn


def ensure_schema(conn, dimensions: int):
    """
    pgvector 拡張と rag_embeddings テーブルを作成するでごわす。
    すでに存在する場合はエラーにならないよう IF NOT EXISTS 付きで実行するでごわす。
    """
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS rag_embeddings (
                id           bigserial PRIMARY KEY,
                doc_id       text,
                chunk_id     text UNIQUE,
                chunk_index  integer,
                title        text,
                source       text,
                lang         text,
                origin_s3_uri text,
                embedding    vector({dimensions})
            );
            """
        )


def embedding_to_pgvector_literal(vec: List[float]) -> str:
    """
    Python の list[float] を pgvector の文字列表現 '[v1,v2,...]' に変換するでごわす。
    """
    inner = ",".join(str(v) for v in vec)
    return f"[{inner}]"


def upsert_embedding(conn, record: Dict[str, Any], embedding: List[float]):
    """
    1チャンク分のメタ情報＋埋め込みを rag_embeddings に INSERT するでごわす。
    同じ chunk_id がある場合はスキップする簡易版でごわす。
    """
    chunk_id = record.get("chunk_id")
    if not chunk_id:
        raise ValueError("chunk_id がないレコードは想定外でごわす。")

    pg_vec_literal = embedding_to_pgvector_literal(embedding)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM rag_embeddings WHERE chunk_id = %s;",
            (chunk_id,),
        )
        if cur.fetchone():
            print(f"[SKIP] 既に登録済み chunk_id={chunk_id} でごわす。")
            return

        cur.execute(
            """
            INSERT INTO rag_embeddings (
                doc_id,
                chunk_id,
                chunk_index,
                title,
                source,
                lang,
                origin_s3_uri,
                embedding
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s::vector
            );
            """,
            (
                record.get("doc_id"),
                chunk_id,
                record.get("chunk_index"),
                record.get("title"),
                record.get("source"),
                record.get("lang", "ja"),
                record.get("origin_s3_uri"),
                pg_vec_literal,
            ),
        )
        print(f"[OK] INSERT chunk_id={chunk_id} でごわす。")


def main():
    parser = argparse.ArgumentParser(
        description="Bedrock Titan でチャンクを埋め込み、Aurora(pgvector) に INSERT する最小ループでごわす。"
    )
    parser.add_argument(
        "--chunks",
        type=str,
        default="data/corpus/chunks/chunks_local.jsonl",
        help="チャンクファイル (JSONL) のパスでごわす。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="試験的に処理するチャンク数の上限でごわす。（デフォルト5件）",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=os.environ.get("AWS_REGION", "ap-northeast-1"),
        help="Bedrock を利用するリージョンでごわす。（例: ap-northeast-1）",
    )
    parser.add_argument(
        "--model-id",
        type=str,
        default="amazon.titan-embed-text-v2:0",
        help="Bedrock の埋め込みモデルIDでごわす。",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=1024,
        help="埋め込みベクトルの次元数でごわす。（v2 のデフォルト 1024）",
    )
    args = parser.parse_args()

    chunks_path = Path(args.chunks)
    if not chunks_path.exists():
        raise FileNotFoundError(f"チャンクファイルが見つからんでごわす: {chunks_path}")

    print(f"[INFO] チャンクファイル: {chunks_path} でごわす。")
    print(f"[INFO] AWS Region: {args.region}, Model ID: {args.model_id} でごわす。")

    bedrock_client = get_bedrock_client(args.region)

    conn = get_pg_connection()
    try:
        ensure_schema(conn, args.dimensions)

        processed = 0
        for record in iter_chunks(chunks_path, limit=args.limit):
            text = record.get("text", "")
            if not text:
                print(f"[WARN] text が空のためスキップするでごわす: chunk_id={record.get('chunk_id')}")
                continue

            embedding = embed_with_titan(
                bedrock_client,
                text=text,
                model_id=args.model_id,
                dimensions=args.dimensions,
                normalize=True,
            )

            upsert_embedding(conn, record, embedding)
            processed += 1

        print(f"[DONE] 処理完了でごわす。processed_chunks={processed}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

