# data/scripts/inject_s3_uri.py
import json, pathlib, os
from pathlib import Path

BUCKET = os.environ.get("BUCKET")
PREFIX = f"s3://{BUCKET}/corpus/cleaned/"

meta_in = Path("data/metadata/manifest_enriched.jsonl")
meta_out = Path("data/metadata/manifest.jsonl")

def main():
    with meta_in.open(encoding="utf-8") as fin, meta_out.open("w", encoding="utf-8") as fout:
        for line in fin:
            obj = json.loads(line)
            local = pathlib.Path(obj["local_path"]).name
            obj["s3_uri"] = PREFIX + local
            obj.pop("local_path", None)
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()

