#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any


def chunk_text(text: str, max_chars: int, overlap: int) -> List[str]:
    """
    シンプルな文字数ベースのチャンク分割でごわす。
    """
    chunks: List[str] = []
    start = 0
    text_length = len(text)

    if text_length == 0:
        return chunks

    if overlap >= max_chars:
        raise ValueError("overlap は max_chars より小さい必要があるでごわす。")

    while start < text_length:
        end = min(start + max_chars, text_length)
        chunk = text[start:end]
        chunks.append(chunk)

        if end == text_length:
            break

        start = end - overlap

    return chunks


def load_manifest(path: Path) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            docs.append(json.loads(line))
    return docs


def main():
    parser = argparse.ArgumentParser(description="manifest.jsonl に基づいて cleaned テキストをチャンクに分割するでごわす。")
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/metadata/manifest.jsonl",
        help="入力 manifest.jsonl のパスでごわす。",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/corpus/chunks/chunks_local.jsonl",
        help="出力 chunks_local.jsonl のパスでごわす。",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1200,
        help="1チャンクの最大文字数でごわす。",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=240,
        help="チャンク間のオーバーラップでごわす。",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_path = Path(args.output)

    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest が見つからんでごわす: {manifest_path}")

    docs = load_manifest(manifest_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_docs = 0
    total_chunks = 0

    with output_path.open("w", encoding="utf-8") as out_f:
        for doc in docs:
            total_docs += 1

            # ★ manifest.jsonl には s3_uri のみ。ファイル本体は data/cleaned/ にあるでごわす。
            s3_uri = doc.get("s3_uri")
            if not s3_uri:
                print(f"[WARN] s3_uri がないのでスキップするでごわす: doc_id={doc.get('doc_id')}")
                continue

            filename = os.path.basename(s3_uri)
            text_path = Path("data/cleaned") / filename

            if not text_path.exists():
                print(f"[WARN] テキストファイルが見つからんでごわす: {text_path}")
                continue

            with text_path.open("r", encoding="utf-8") as tf:
                text = tf.read()

            chunks = chunk_text(text, max_chars=args.max_chars, overlap=args.overlap)
            if not chunks:
                print(f"[INFO] 空文書のためチャンクなしでごわす: doc_id={doc.get('doc_id')}")
                continue

            for idx, chunk_text_value in enumerate(chunks):
                total_chunks += 1
                chunk_record = {
                    "doc_id": doc.get("doc_id"),
                    "chunk_id": f"{doc.get('doc_id')}_chunk_{idx:04d}",
                    "chunk_index": idx,
                    "text": chunk_text_value,
                    "num_chars": len(chunk_text_value),
                    "title": doc.get("title"),
                    "source": doc.get("source"),
                    "lang": doc.get("lang", "ja"),
                    "origin_s3_uri": s3_uri,
                }
                out_f.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")

    print(f"[DONE] 文書数: {total_docs}, チャンク総数: {total_chunks} でごわす。")
    print(f"[DONE] 出力: {output_path} でごわす。")


if __name__ == "__main__":
    main()

