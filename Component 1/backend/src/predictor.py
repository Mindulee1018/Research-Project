import os
import json
import torch
import numpy as np
import pandas as pd
from optimum.onnxruntime import ORTModelForTokenClassification
from transformers import AutoTokenizer, AutoModelForSequenceClassification

LABEL2ID = {'HATE': 0, 'DISINFO': 1, 'NORMAL': 2}
ID2LABEL = {0: 'HATE', 1: 'DISINFO', 2: 'NORMAL'}
TAG2ID = {'O': 0, 'B-HATE': 1, 'I-HATE': 2}
ID2TAG = {0: 'O', 1: 'B-HATE', 2: 'I-HATE'}

# Thresholds
HATE_CLASSIFY_THRESHOLD = 0.65
HATE_TOKEN_THRESHOLD = 0.55
DISINFO_THRESHOLD = 0.60

# HuggingFace repos
CLF_REPO = "Imaya2002/sinhala-hate-classifier-v2"
TOKEN_REPO = "Imaya2002/sinhala-hate-word-detector"

# Local data paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAIN_DATA_PATH = os.path.join(BASE_DIR, 'Data', 'train_set.csv')
BIO_DATA_PATH = os.path.join(BASE_DIR, 'Data', 'bio_train_dataset.json')

# Change "Component 2" if your real folder name is different
COMPONENT2_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Component 2'))
LEXICON_STORE_PATH = os.path.join(COMPONENT2_DIR, 'artifacts', 'lexicon_store.json')
MANUAL_ALIASES_PATH = os.path.join(COMPONENT2_DIR, 'artifacts', 'manual_aliases.json')

FALSE_POSITIVE_WORDS = {
    'වැඩ', 'weda', 'onna', 'oni', 'hatida', 'naw', 'tika',
    'ganna', 'kela', 'eka', 'inna', 'wenna', 'kiyala',
    'karapan', 'nethi', 'nathara', 'dakinna', 'wenwa',
    'bad', 'hate', 'sad', 'mad', 'die', 'kill', 'fight',
}


class SinhalaHateDetector:
    def __init__(self):
        self.device = 'cpu'

        print(">>> predictor.py loaded from:", __file__)

        print("Loading tokenizer from HuggingFace...")
        self.tokenizer = AutoTokenizer.from_pretrained(CLF_REPO)

        print("Loading classifier model (PyTorch)...")
        self.clf_model = AutoModelForSequenceClassification.from_pretrained(CLF_REPO)
        self.clf_model.eval()

        print("Loading token classifier model (ONNX)...")
        self.token_model = ORTModelForTokenClassification.from_pretrained(TOKEN_REPO)

        print("Loading manual aliases...")
        self.manual_aliases = self._load_manual_aliases()

        print("Loading incremental lexicon terms...")
        self.incremental_terms = self._load_incremental_lexicon_terms()

        print("Building hate word set...")
        self.hate_word_set = self._build_hate_word_set()

        print("New learned terms from Component 2:")
        for w in sorted(self.incremental_terms):
            print("-", w)
        print("Total new learned terms:", len(self.incremental_terms))

        print(f"Hate word set: {len(self.hate_word_set)} unique tokens")
        print("✅ Detector ready!\n")

    def _normalize_token(self, token: str) -> str:
        return str(token).strip().lower()

    def _load_manual_aliases(self):
        print("Checking manual aliases path:", MANUAL_ALIASES_PATH)
        print("Manual aliases file exists:", os.path.exists(MANUAL_ALIASES_PATH))

        if not os.path.exists(MANUAL_ALIASES_PATH):
            return {}

        try:
            with open(MANUAL_ALIASES_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict):
                clean = {}
                for k, v in data.items():
                    kk = self._normalize_token(k)
                    vv = self._normalize_token(v)
                    if kk and vv:
                        clean[kk] = vv
                print("Loaded manual aliases:", len(clean))
                return clean

        except Exception as e:
            print(f"Warning: failed to load manual aliases: {e}")

        return {}

    def _apply_alias(self, token: str) -> str:
        t = self._normalize_token(token)
        return self.manual_aliases.get(t, t)

    def _load_incremental_lexicon_terms(self):
        learned_terms = set()

        print("Checking Component 2 dir:", COMPONENT2_DIR)
        print("Checking lexicon path:", LEXICON_STORE_PATH)
        print("Lexicon file exists:", os.path.exists(LEXICON_STORE_PATH))

        if not os.path.exists(LEXICON_STORE_PATH):
            print(">>> lexicon file not found")
            return learned_terms

        try:
            with open(LEXICON_STORE_PATH, 'r', encoding='utf-8') as f:
                payload = json.load(f)

            entries = payload.get("entries", {})
            print("Total entries in lexicon file:", len(entries))

            for i, (term, stats) in enumerate(entries.items()):
                print("TERM:", term, "STATS:", stats)
                if i >= 10:
                    break

            for term, stats in entries.items():
                t = self._normalize_token(term)
                if not t or t in FALSE_POSITIVE_WORDS:
                    continue

                hate_count = int(stats.get("hate_count", 0))
                total_count = int(stats.get("total_count", 0))
                weight = float(stats.get("weight", 0.0))

                hate_ratio = (hate_count / total_count) if total_count > 0 else 0.0

                print(
                    "DEBUG TERM:",
                    t,
                    "hate_count=", hate_count,
                    "total_count=", total_count,
                    "hate_ratio=", hate_ratio,
                    "weight=", weight,
                )

                if hate_count >= 1 and total_count >= 2 and hate_ratio >= 0.60:
                    learned_terms.add(self._apply_alias(t))

        except Exception as e:
            print(f"Warning: failed to load incremental lexicon: {e}")

        print("Selected learned terms:", sorted(list(learned_terms))[:50])
        print("Selected learned terms count:", len(learned_terms))
        return learned_terms

    def _build_hate_word_set(self):
        hate_words = set()

        if os.path.exists(BIO_DATA_PATH):
            with open(BIO_DATA_PATH, 'r', encoding='utf-8') as f:
                bio_data = json.load(f)

            for example in bio_data:
                for token, tag in zip(example['tokens'], example['tags']):
                    if tag in ('B-HATE', 'I-HATE'):
                        w = self._apply_alias(token)
                        if w and w not in FALSE_POSITIVE_WORDS:
                            hate_words.add(w)

        if os.path.exists(TRAIN_DATA_PATH):
            df = pd.read_csv(TRAIN_DATA_PATH, encoding='utf-8-sig')
            if 'Word Identified' in df.columns:
                for val in df['Word Identified'].dropna():
                    for w in str(val).split(','):
                        w = self._normalize_token(w)
                        if w in {
                            'implied', 'implied threat', 'implied insult',
                            'implied mother insult', 'implied hate', 'nan', ''
                        }:
                            continue
                        if w in FALSE_POSITIVE_WORDS:
                            continue

                        for token in w.split():
                            t = self._apply_alias(token)
                            if t and t not in FALSE_POSITIVE_WORDS:
                                hate_words.add(t)

        hate_words.update(self.incremental_terms)

        hate_words.discard('')
        hate_words.discard('nan')
        return hate_words

    def _get_hate_words_token_model(self, comment):
        words = comment.strip().split()
        if not words:
            return []

        try:
            token_inputs = self.tokenizer(
                words,
                return_tensors='pt',
                truncation=True,
                max_length=128,
                is_split_into_words=True,
                padding=True,
            )

            token_logits = self.token_model(**token_inputs).logits
            probs = torch.softmax(torch.tensor(np.array(token_logits)), dim=-1)[0]
            token_preds = token_logits.argmax(axis=-1)[0].tolist()
            word_ids = token_inputs.word_ids()

            seen_words = set()
            hate_words = []

            for idx, word_id in enumerate(word_ids):
                if word_id is None or word_id in seen_words:
                    continue

                seen_words.add(word_id)
                tag = ID2TAG[token_preds[idx]]
                hate_prob = float(probs[idx][1]) + float(probs[idx][2])

                if tag in ('B-HATE', 'I-HATE') or hate_prob > HATE_TOKEN_THRESHOLD:
                    word = words[word_id]
                    canon = self._apply_alias(word)
                    if canon and canon not in FALSE_POSITIVE_WORDS:
                        hate_words.append(word)

            return hate_words

        except Exception as e:
            print("Token model error:", e)
            return []

    def _get_hate_words_pattern(self, comment):
        words = comment.strip().split()
        found = []

        for w in words:
            canon = self._apply_alias(w)
            if canon in self.hate_word_set and canon not in FALSE_POSITIVE_WORDS:
                found.append(w)

        return found

    def _get_hate_words_combined(self, comment):
        token_hate = self._get_hate_words_token_model(comment)
        pattern_hate = self._get_hate_words_pattern(comment)

        combined = list(token_hate)
        seen = {self._normalize_token(w) for w in combined}

        for w in pattern_hate:
            nw = self._normalize_token(w)
            if nw not in seen:
                combined.append(w)
                seen.add(nw)

        return combined

    def predict(self, comment):
        if not comment or len(comment.strip()) < 3:
            return 'NORMAL', []

        inputs = self.tokenizer(
            comment,
            return_tensors='pt',
            truncation=True,
            max_length=128,
            padding=True,
        )

        with torch.no_grad():
            logits = self.clf_model(**inputs).logits

        probs = torch.softmax(logits, dim=-1)[0]
        hate_prob = float(probs[0])
        dis_prob = float(probs[1])

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
                'comment': comment,
                'label': label,
                'hate_words': ', '.join(hate_words) if hate_words else '',
            })

            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(comments)} comments...")

        return results

    def check_learned_word(self, word):
        w = self._apply_alias(word)
        print("Input word:", word)
        print("Canonical word:", w)
        print("In incremental learned terms:", w in self.incremental_terms)
        print("In full hate word set:", w in self.hate_word_set)