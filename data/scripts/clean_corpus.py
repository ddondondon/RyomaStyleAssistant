# data/scripts/clean_corpus.py
import os, re, json, hashlib, math
from pathlib import Path
from datetime import datetime, timezone, timedelta
import chardet
from unidecode import unidecode
import ftfy
from slugify import slugify
import tiktoken

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/cleaned")
META_DIR = Path("data/metadata")
OUT_DIR.mkdir(parents=True, exist_ok=True)
META_DIR.mkdir(parents=True, exist_ok=True)

JST = timezone(timedelta(hours=9))

enc = tiktoken.get_encoding("cl100k_base")  # ざっくりトークン見積もり

def detect_and_read(p: Path) -> str:
    raw = p.read_bytes()
    det = chardet.detect(raw)
    text = raw.decode(det["encoding"] or "utf-8", errors="ignore")
    return text

def normalize_text(text: str) -> str:
    # 1) 変な制御文字除去
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # 2) 改行統一
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 3) ftfy で文字化け修復
    text = ftfy.fix_text(text)
    # 4) 先頭末尾の空白整理 & 連続空行縮約
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    return text

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def estimate_tokens(s: str) -> int:
    # 大まかな見積り
    return len(enc.encode(s))

def main():
    records = []
    seen_hash = set()
    for p in RAW_DIR.glob("**/*"):
        if not p.is_file():
            continue
        try:
            text = detect_and_read(p)
            text = normalize_text(text)
            if not text:
                continue
            h = sha256_hex(text)
            if h in seen_hash:
                # 完全重複はスキップ
                continue
            seen_hash.add(h)

            # ファイル名スラグ
            base = slugify(p.stem) or "doc"
            out_name = f"{base}.txt"
            out_path = OUT_DIR / out_name
            # 衝突回避
            i = 1
            while out_path.exists():
                out_path = OUT_DIR / f"{base}-{i}.txt"; i += 1

            out_path.write_text(text, encoding="utf-8")

            rec = {
                "doc_id": h[:16],  # 簡易ID
                "title": p.stem,
                "lang": "ja",
                "source": "unknown",  # 後で上書き可
                "license": "unknown",
                "created_at": datetime.now(JST).isoformat(),
                "hash": h,
                "local_path": str(out_path),
                "char_count": len(text),
                "token_estimate": estimate_tokens(text),
                "tags": ["ryoma","bakumatsu"]
            }
            records.append(rec)
        except Exception as e:
            (META_DIR/"clean_errors.log").open("a").write(f"{p}\t{e}\n")

    # 中間メタをJSONLで保存
    with (META_DIR/"manifest_local.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
