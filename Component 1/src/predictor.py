# ============================================================
# predictor.py — Label + Hate Word Prediction
# ============================================================

import os
import json
import torch
import pandas as pd
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    AutoModelForTokenClassification,
)

LABEL2ID = {'HATE': 0, 'DISINFO': 1, 'NORMAL': 2}
ID2LABEL = {0: 'HATE', 1: 'DISINFO', 2: 'NORMAL'}
TAG2ID   = {'O': 0, 'B-HATE': 1, 'I-HATE': 2}
ID2TAG   = {0: 'O', 1: 'B-HATE', 2: 'I-HATE'}
HATE_PROB_THRESHOLD = 0.4


class SinhalaHateDetector:
    """
    Full pipeline for Sinhala hate speech and disinformation detection.

    Usage:
        detector = SinhalaHateDetector(
            clf_model_path   = 'Models/clf_model_final',
            token_model_path = 'Models/token_model_final',
            train_data_path  = 'Data/train_set.csv',
            bio_data_path    = 'Data/bio_train_dataset.json',
        )
        label, hate_words = detector.predict("ballo thopi hora kala")
    """

    def __init__(self, clf_model_path, token_model_path, train_data_path, bio_data_path):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {self.device}")

        print("Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(clf_model_path)

        print("Loading classifier model...")
        self.clf_model = AutoModelForSequenceClassification.from_pretrained(
            clf_model_path, num_labels=3, id2label=ID2LABEL, label2id=LABEL2ID,
        ).to(self.device)
        self.clf_model.eval()

        print("Loading token classifier model...")
        self.token_model = AutoModelForTokenClassification.from_pretrained(
            token_model_path, num_labels=3, id2label=ID2TAG, label2id=TAG2ID,
        ).to(self.device)
        self.token_model.eval()

        print("Building hate word set...")
        self.hate_word_set = self._build_hate_word_set(train_data_path, bio_data_path)
        print(f"Hate word set: {len(self.hate_word_set)} unique tokens")
        print("Detector ready!\n")

    def _build_hate_word_set(self, train_data_path, bio_data_path):
        hate_words = set()

        if os.path.exists(bio_data_path):
            with open(bio_data_path, 'r', encoding='utf-8') as f:
                bio_data = json.load(f)
            for example in bio_data:
                for token, tag in zip(example['tokens'], example['tags']):
                    if tag in ('B-HATE', 'I-HATE'):
                        hate_words.add(token.lower().strip())

        if os.path.exists(train_data_path):
            df = pd.read_csv(train_data_path, encoding='utf-8-sig')
            if 'Word Identified' in df.columns:
                for val in df['Word Identified'].dropna():
                    for w in str(val).split(','):
                        w = w.strip().lower()
                        if w and w not in {'implied', 'implied threat', 'implied insult',
                                           'implied mother insult', 'implied hate', 'nan', ''}:
                            for token in w.split():
                                hate_words.add(token.strip())

        hate_words.discard('')
        hate_words.discard('nan')
        return hate_words

    def _get_hate_words_token_model(self, comment):
        words = comment.strip().split()
        if not words:
            return []
        try:
            token_inputs = self.tokenizer(
                words, return_tensors='pt', truncation=True,
                max_length=128, is_split_into_words=True, padding=True,
            ).to(self.device)

            with torch.no_grad():
                token_logits = self.token_model(**token_inputs).logits

            probs       = torch.softmax(token_logits, dim=-1)[0]
            token_preds = torch.argmax(token_logits, dim=-1)[0].tolist()
            word_ids    = token_inputs.word_ids()
            seen_words  = set()
            hate_words  = []

            for idx, word_id in enumerate(word_ids):
                if word_id is None or word_id in seen_words:
                    continue
                seen_words.add(word_id)
                tag       = ID2TAG[token_preds[idx]]
                hate_prob = probs[idx][1].item() + probs[idx][2].item()
                if tag in ('B-HATE', 'I-HATE') or hate_prob > HATE_PROB_THRESHOLD:
                    hate_words.append(words[word_id])
            return hate_words
        except Exception:
            return []

    def _get_hate_words_pattern(self, comment):
        words = comment.strip().split()
        return [w for w in words if w.lower().strip() in self.hate_word_set]

    def _get_hate_words_combined(self, comment):
        token_hate   = self._get_hate_words_token_model(comment)
        pattern_hate = self._get_hate_words_pattern(comment)
        combined = list(token_hate)
        seen = {w.lower() for w in combined}
        for w in pattern_hate:
            if w.lower() not in seen:
                combined.append(w)
                seen.add(w.lower())
        return combined

    def predict(self, comment):
        if not comment or len(comment.strip()) < 3:
            return 'NORMAL', []

        inputs = self.tokenizer(
            comment, return_tensors='pt', truncation=True,
            max_length=128, padding=True,
        ).to(self.device)

        with torch.no_grad():
            logits = self.clf_model(**inputs).logits

        pred_label = ID2LABEL[torch.argmax(logits).item()]
        hate_words = self._get_hate_words_combined(comment) if pred_label == 'HATE' else []
        return pred_label, hate_words

    def predict_batch(self, comments):
        results = []
        for i, comment in enumerate(comments):
            label, hate_words = self.predict(comment)
            results.append({
                'comment':    comment,
                'label':      label,
                'hate_words': ', '.join(hate_words) if hate_words else '',
            })
            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(comments)} comments...")
        return results
