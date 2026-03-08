import os
import json
import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH = "data/sinhala_harmful_content_dataset_12000_balanced.csv"
OUTPUT_DIR = "analysis_outputs"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_data(path):
    df = pd.read_csv(path)
    if "text" not in df.columns or "label" not in df.columns:
        raise ValueError("Dataset must contain 'text' and 'label' columns.")
    return df


def add_text_features(df):
    df = df.copy()
    df["char_count"] = df["text"].astype(str).apply(len)
    df["word_count"] = df["text"].astype(str).apply(lambda x: len(x.split()))
    df["has_emoji"] = df["text"].astype(str).str.contains(r"[^\w\s,.;:!?'-]", regex=True)
    df["has_english"] = df["text"].astype(str).str.contains(r"[A-Za-z]", regex=True)
    return df


def dataset_summary(df):
    summary = {
        "total_samples": int(len(df)),
        "label_distribution": df["label"].value_counts().to_dict(),
        "avg_char_count": float(df["char_count"].mean()),
        "avg_word_count": float(df["word_count"].mean()),
        "max_char_count": int(df["char_count"].max()),
        "min_char_count": int(df["char_count"].min()),
        "samples_with_emoji": int(df["has_emoji"].sum()),
        "samples_with_english": int(df["has_english"].sum()),
    }

    per_class = (
        df.groupby("label")[["char_count", "word_count"]]
        .mean()
        .round(2)
        .to_dict(orient="index")
    )
    summary["per_class_text_stats"] = per_class
    return summary


def save_summary(summary):
    out_path = os.path.join(OUTPUT_DIR, "dataset_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_path}")


def save_examples(df):
    examples = (
        df.groupby("label", group_keys=False)
        .head(5)[["text", "label"]]
        .reset_index(drop=True)
    )
    out_path = os.path.join(OUTPUT_DIR, "sample_examples.csv")
    examples.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {out_path}")


def plot_label_distribution(df):
    plt.figure(figsize=(8, 5))
    df["label"].value_counts().plot(kind="bar")
    plt.title("Label Distribution")
    plt.xlabel("Class")
    plt.ylabel("Count")
    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "label_distribution.png")
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved: {out_path}")


def plot_word_count_by_label(df):
    plt.figure(figsize=(8, 5))
    for label in df["label"].unique():
        subset = df[df["label"] == label]
        plt.hist(subset["word_count"], bins=30, alpha=0.5, label=label)
    plt.title("Word Count Distribution by Label")
    plt.xlabel("Word Count")
    plt.ylabel("Frequency")
    plt.legend()
    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "word_count_by_label.png")
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved: {out_path}")


def plot_char_count_by_label(df):
    plt.figure(figsize=(8, 5))
    for label in df["label"].unique():
        subset = df[df["label"] == label]
        plt.hist(subset["char_count"], bins=30, alpha=0.5, label=label)
    plt.title("Character Count Distribution by Label")
    plt.xlabel("Character Count")
    plt.ylabel("Frequency")
    plt.legend()
    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "char_count_by_label.png")
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved: {out_path}")


def save_classwise_stats(df):
    stats = (
        df.groupby("label")
        .agg(
            sample_count=("label", "count"),
            avg_char_count=("char_count", "mean"),
            avg_word_count=("word_count", "mean"),
            emoji_count=("has_emoji", "sum"),
            english_mixed_count=("has_english", "sum"),
        )
        .round(2)
        .reset_index()
    )
    out_path = os.path.join(OUTPUT_DIR, "classwise_stats.csv")
    stats.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {out_path}")


def main():
    df = load_data(DATA_PATH)
    df = add_text_features(df)

    summary = dataset_summary(df)
    save_summary(summary)
    save_examples(df)
    save_classwise_stats(df)

    plot_label_distribution(df)
    plot_word_count_by_label(df)
    plot_char_count_by_label(df)

    print("\n=== DATASET SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()