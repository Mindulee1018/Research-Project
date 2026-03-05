import os
import json
import unicodedata
import morfessor

MODEL_PATH = "artifacts/morfessor_model.bin"
VOCAB_PATH = "artifacts/morfessor_vocab.json"

def normalize_surface(term: str) -> str:
    if term is None:
        return ""
    s = str(term).strip()
    s = unicodedata.normalize("NFC", s)
    return s

def save_vocab(counter: dict[str, int], path: str = VOCAB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(counter, f, ensure_ascii=False, indent=2)

def load_vocab(path: str = VOCAB_PATH) -> dict[str, int]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def train_morfessor(counter: dict[str, int], model_path: str = MODEL_PATH):
    """
    counter: {word: count}
    Train Morfessor and save binary model.
    """
    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    model = morfessor.BaselineModel()
    data = [(int(c), normalize_surface(w)) for w, c in counter.items() if w and int(c) > 0]

    model.load_data(data)
    model.train_batch()

    io = morfessor.MorfessorIO()
    io.write_binary_model_file(model_path, model)
    return model

def load_morfessor(model_path: str = MODEL_PATH):
    """
    Return a Morfessor model object or None.
    Handles cases where previous code saved/loaded incorrectly.
    """
    if not os.path.exists(model_path):
        return None

    io = morfessor.MorfessorIO()
    loaded = io.read_binary_model_file(model_path)

    # Some versions may return (model, meta) or just model.
    if isinstance(loaded, tuple) and len(loaded) > 0:
        loaded = loaded[0]

    # If it isn't a model object, treat as broken
    if not hasattr(loaded, "viterbi_segment"):
        return None

    return loaded

def stem_with_morfessor(model, word: str) -> str:
    """
    Returns first segment (stem-like key).
    Safe: if model is None or invalid, returns the word itself.
    """
    w = normalize_surface(word)
    if not w:
        return ""

    # safety: if model is accidentally a string/path, ignore it
    if model is None or isinstance(model, str) or not hasattr(model, "viterbi_segment"):
        return w

    segments, _ = model.viterbi_segment(w)
    return segments[0] if segments else w
