# pipeline.py
import os
import pandas as pd
from scraper import scrape_youtube_comments
from cleaner import clean_comment, is_valid_comment
from predictor import SinhalaHateDetector

BASE_DIR         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLF_MODEL_PATH   = os.path.join(BASE_DIR, "models", "clf_model_final")
TOKEN_MODEL_PATH = os.path.join(BASE_DIR, "models", "token_model_final")
TRAIN_DATA_PATH  = os.path.join(BASE_DIR, "data",   "train_set.csv")
BIO_DATA_PATH    = os.path.join(BASE_DIR, "data",   "bio_train_dataset.json")
OUTPUTS_DIR      = os.path.join(BASE_DIR, "outputs")

def run_pipeline(youtube_url, max_comments=500, output_filename=None):
    print("=" * 60)
    print("  Sinhala Hate Speech & Disinformation Detection Pipeline")
    print("=" * 60)

    detector = SinhalaHateDetector(
        clf_model_path=CLF_MODEL_PATH,
        token_model_path=TOKEN_MODEL_PATH,
        train_data_path=TRAIN_DATA_PATH,
        bio_data_path=BIO_DATA_PATH,
    )

    print(f"Scraping from: {youtube_url}")
    raw_comments = scrape_youtube_comments(youtube_url, max_comments)
    if not raw_comments:
        print("No comments found!")
        return None

    results = []
    for i, raw_comment in enumerate(raw_comments):
        cleaned = clean_comment(raw_comment)
        if not is_valid_comment(cleaned):
            continue
        label, hate_words = detector.predict(cleaned)
        results.append({
            "Original Comment": raw_comment,
            "Cleaned Comment":  cleaned,
            "Label":            label,
            "Hate":             1 if label == "HATE"    else 0,
            "Disinfo":          1 if label == "DISINFO" else 0,
            "Normal":           1 if label == "NORMAL"  else 0,
            "Hate Words":       ", ".join(hate_words) if hate_words else "",
        })
        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(raw_comments)} comments...")

    results_df = pd.DataFrame(results)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    if output_filename is None:
        video_id = youtube_url.split("v=")[-1].split("&")[0].split("/")[-1]
        output_filename = f"results_{video_id}.csv"
    output_path = os.path.join(OUTPUTS_DIR, output_filename)
    results_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Total: {len(results_df)} | HATE: {results_df["Hate"].sum()} | DISINFO: {results_df["Disinfo"].sum()} | NORMAL: {results_df["Normal"].sum()}")
    print(f"Saved to: {output_path}")
    return results_df

if __name__ == "__main__":
    YOUTUBE_URL = "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
    df = run_pipeline(youtube_url=YOUTUBE_URL, max_comments=500, output_filename="youtube_results.csv")
