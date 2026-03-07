# predictor.py
import os
import json
import torch
import numpy as np
import pandas as pd
from optimum.onnxruntime import ORTModelForTokenClassification
from transformers import AutoTokenizer, AutoModelForSequenceClassification

LABEL2ID = {'HATE': 0, 'DISINFO': 1, 'NORMAL': 2}
ID2LABEL = {0: 'HATE', 1: 'DISINFO', 2: 'NORMAL'}
TAG2ID   = {'O': 0, 'B-HATE': 1, 'I-HATE': 2}
ID2TAG   = {0: 'O', 1: 'B-HATE', 2: 'I-HATE'}

# ── Thresholds ────────────────────────────────────────────────
HATE_CLASSIFY_THRESHOLD = 0.65
HATE_TOKEN_THRESHOLD    = 0.55
DISINFO_THRESHOLD       = 0.60

# ── HuggingFace repos ─────────────────────────────────────────
CLF_REPO   = "Imaya2002/sinhala-hate-classifier-v2"   # PyTorch
TOKEN_REPO = "Imaya2002/sinhala-hate-word-detector"   # ONNX

# ── Local data paths ──────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAIN_DATA_PATH = os.path.join(BASE_DIR, 'Data', 'train_set.csv')
BIO_DATA_PATH   = os.path.join(BASE_DIR, 'Data', 'bio_train_dataset.json')

# ── False positive hate words to EXCLUDE ─────────────────────
FALSE_POSITIVE_WORDS = {
    'වැඩ', 'weda', 'onna', 'oni', 'hatida', 'naw', 'tika',
    'ganna', 'kela', 'eka', 'inna', 'wenna', 'kiyala',
    'karapan', 'nethi', 'nathara', 'dakinna', 'wenwa',
    'bad', 'hate', 'sad', 'mad', 'die', 'kill', 'fight',
}


class SinhalaHateDetector:
    def __init__(self):
        self.device = 'cpu'
        print("Loading tokenizer from HuggingFace...")
        self.tokenizer = AutoTokenizer.from_pretrained(CLF_REPO)

        print("Loading classifier model (PyTorch)...")
        self.clf_model = AutoModelForSequenceClassification.from_pretrained(CLF_REPO)
        self.clf_model.eval()

        print("Loading token classifier model (ONNX)...")
        self.token_model = ORTModelForTokenClassification.from_pretrained(TOKEN_REPO)

        print("Building hate word set...")
        self.hate_word_set = self._build_hate_word_set()
        print(f"Hate word set: {len(self.hate_word_set)} unique tokens")
        print("✅ Detector ready!\n")

    def _build_hate_word_set(self):
        hate_words = set()
        if os.path.exists(BIO_DATA_PATH):
            with open(BIO_DATA_PATH, 'r', encoding='utf-8') as f:
                bio_data = json.load(f)
            for example in bio_data:
                for token, tag in zip(example['tokens'], example['tags']):
                    if tag in ('B-HATE', 'I-HATE'):
                        w = token.lower().strip()
                        if w and w not in FALSE_POSITIVE_WORDS:
                            hate_words.add(w)

        if os.path.exists(TRAIN_DATA_PATH):
            df = pd.read_csv(TRAIN_DATA_PATH, encoding='utf-8-sig')
            if 'Word Identified' in df.columns:
                for val in df['Word Identified'].dropna():
                    for w in str(val).split(','):
                        w = w.strip().lower()
                        if w and w not in {'implied', 'implied threat', 'implied insult',
                                           'implied mother insult', 'implied hate', 'nan', ''} \
                                and w not in FALSE_POSITIVE_WORDS:
                            for token in w.split():
                                t = token.strip()
                                if t and t not in FALSE_POSITIVE_WORDS:
                                    hate_words.add(t)
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
            )
            token_logits = self.token_model(**token_inputs).logits
            probs        = torch.softmax(torch.tensor(np.array(token_logits)), dim=-1)[0]
            token_preds  = token_logits.argmax(axis=-1)[0].tolist()
            word_ids     = token_inputs.word_ids()
            seen_words   = set()
            hate_words   = []

            for idx, word_id in enumerate(word_ids):
                if word_id is None or word_id in seen_words:
                    continue
                seen_words.add(word_id)
                tag       = ID2TAG[token_preds[idx]]
                hate_prob = float(probs[idx][1]) + float(probs[idx][2])
                if (tag in ('B-HATE', 'I-HATE') or hate_prob > HATE_TOKEN_THRESHOLD):
                    word = words[word_id]
                    if word.lower().strip() not in FALSE_POSITIVE_WORDS:
                        hate_words.append(word)
            return hate_words
        except Exception:
            return []

    def _get_hate_words_pattern(self, comment):
        words = comment.strip().split()
        return [
            w for w in words
            if w.lower().strip() in self.hate_word_set
            and w.lower().strip() not in FALSE_POSITIVE_WORDS
        ]

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
            comment, return_tensors='pt',
            truncation=True, max_length=128, padding=True,
        )

        with torch.no_grad():
            logits = self.clf_model(**inputs).logits

        probs     = torch.softmax(logits, dim=-1)[0]
        hate_prob = float(probs[0])
        dis_prob  = float(probs[1])

        if hate_prob >= HATE_CLASSIFY_THRESHOLD:
            pred_label = 'HATE'
        elif dis_prob >= DISINFO_THRESHOLD:
            pred_label = 'DISINFO'
        else:
            pred_label = 'NORMAL'

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