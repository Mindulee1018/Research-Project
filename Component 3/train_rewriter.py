import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer

BANK_CSV = "rewrites_bank_1000.csv"
OUT_DIR = "rewrite_index"
EMB_FILE = os.path.join(OUT_DIR, "embeddings.npy")
META_FILE = os.path.join(OUT_DIR, "bank.parquet")

# Sinhala-friendly multilingual embedder (good default)
EMBED_MODEL = os.environ.get("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(BANK_CSV)
    required = {"type", "unsafe", "clean"}
    if not required.issubset(df.columns):
        raise ValueError(f"CSV must contain columns: {required}. Found: {list(df.columns)}")

    df["type"] = df["type"].astype(str).str.upper().str.strip()
    df["unsafe"] = df["unsafe"].astype(str)
    df["clean"] = df["clean"].astype(str)

    model = SentenceTransformer(EMBED_MODEL)

    # We embed UNSAFE examples to match user unsafe input semantically
    embs = model.encode(df["unsafe"].tolist(), normalize_embeddings=True, show_progress_bar=True)
    embs = np.asarray(embs, dtype=np.float32)

    np.save(EMB_FILE, embs)
    df.to_parquet(META_FILE, index=False)

    print("✅ Saved:", EMB_FILE)
    print("✅ Saved:", META_FILE)
    print("✅ Embed model:", EMBED_MODEL)
    print("Rows:", len(df))

if __name__ == "__main__":
    main()
