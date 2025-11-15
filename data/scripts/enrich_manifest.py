# data/scripts/enrich_manifest.py
import csv, json, re
from pathlib import Path

META = Path("data/metadata")
SRC_CSV = META / "source_log.csv"
MANIFEST_IN  = META / "manifest_local.jsonl"
MANIFEST_OUT = META / "manifest_enriched.jsonl"

# タイトル列の候補（CSV側の表記ゆれ吸収）
TITLE_KEYS = ("title", "name", "作品名", "Title")

def normalize_header(name: str) -> str:
    # 小文字化＋前後空白削除＋全角空白→半角空白
    name = (name or "").replace("\u3000", " ").strip().lower()
    # 連続空白を1つに
    name = re.sub(r"\s+", " ", name)
    return name

def load_source_map():
    m = {}
    if not SRC_CSV.exists():
        raise FileNotFoundError(f"CSV not found: {SRC_CSV}")

    # utf-8-sig でBOMを吸収
    with SRC_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        raw_headers = next(reader)
        # ヘッダー正規化
        headers = [normalize_header(h) for h in raw_headers]

        # DictReaderを自前で構成
        def row_to_dict(row):
            d = {}
            for k, v in zip(headers, row):
                d[k] = v
            return d

        # タイトル列の実キーを決定（優先順で探索）
        title_key = None
        for cand in TITLE_KEYS:
            cand_norm = normalize_header(cand)
            if cand_norm in headers:
                title_key = cand_norm
                break
        if not title_key:
            raise KeyError(f"no title-like column in CSV headers: {headers}")

        # URL / LICENSE も同様に取得（必須ではない）
        url_key = "url" if "url" in headers else None
        lic_key = "license" if "license" in headers else None

        # データ部を読む
        for row in reader:
            d = row_to_dict(row)
            title = (d.get(title_key) or "").strip()
            if not title:
                continue
            m[title] = {
                "url": d.get(url_key) if url_key else None,
                "license": d.get(lic_key) if lic_key else None,
            }

    return m

def main():
    source_map = load_source_map()
    updated = []
    exact, fuzzy, missing = 0, 0, 0

    # JSONL 側も utf-8-sig で安全読み
    with MANIFEST_IN.open(encoding="utf-8-sig") as fin:
        for line in fin:
            if not line.strip():
                continue
            doc = json.loads(line)
            key = (doc.get("title") or "").strip()
            hit = source_map.get(key)

            # 前方一致の簡易あいまいマッチ（5文字閾値）
            if not hit and key:
                for k, v in source_map.items():
                    if k and key.startswith(k[:5]):
                        hit = v
                        fuzzy += 1
                        break

            if hit:
                exact += 1 if fuzzy == 0 else 0
                if hit.get("url"):
                    doc["source"] = hit["url"]
                if hit.get("license"):
                    doc["license"] = hit["license"]
            else:
                missing += 1

            updated.append(doc)

    with MANIFEST_OUT.open("w", encoding="utf-8") as fout:
        for doc in updated:
            fout.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"[enrich_manifest] exact={exact} fuzzy={fuzzy} missing={missing}")
    print(f"[enrich_manifest] wrote -> {MANIFEST_OUT}")

if __name__ == "__main__":
    main()
