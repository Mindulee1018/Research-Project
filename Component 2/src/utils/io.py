import pandas as pd
import ast
import os

REQUIRED = {"hate word", "Hate"}  # change "Hate" -> "hate" if your file uses lowercase

def parse_hate_terms(x):
    if pd.isna(x):
        return []
    s = str(x).strip()

    # empty / [] variants
    if s == "" or s.replace(" ", "") == "[]":
        return []

    # python list string
    if s.startswith("[") and s.endswith("]"):
        try:
            val = ast.literal_eval(s)
            if isinstance(val, list):
                return [str(w).strip() for w in val if str(w).strip()]
        except Exception:
            return []

    # comma-separated fallback (optional but useful)
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        return [p for p in parts if p]

    # single token/phrase
    return [s]

def load_batch_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(
            f"{os.path.basename(path)} missing columns: {missing}. "
            f"Required: {REQUIRED}. Found: {list(df.columns)}"
        )

    df = df.copy()

    # ensure Hate is 0/1 int
    df["Hate"] = pd.to_numeric(df["Hate"], errors="coerce").fillna(0).astype(int)

    # parse terms
    df["terms"] = df["hate word"].apply(parse_hate_terms)

    # batch id
    if "batch_no" in df.columns:
        df["batch_no"] = df["batch_no"].astype(str)
    else:
        df["batch_no"] = os.path.splitext(os.path.basename(path))[0]

    return df
