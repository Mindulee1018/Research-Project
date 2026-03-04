import numpy as np
from collections import Counter
from river.drift import ADWIN

def _safe_prob(counter: Counter, vocab: list[str], alpha: float = 1e-6) -> np.ndarray:
    counts = np.array([counter.get(t, 0) for t in vocab], dtype=np.float64)
    probs = counts + alpha
    probs = probs / probs.sum()
    return probs

def jsd(p: np.ndarray, q: np.ndarray) -> float:
    m = 0.5 * (p + q)
    def kl(a, b):
        return np.sum(a * np.log(a / b))
    return float(0.5 * kl(p, m) + 0.5 * kl(q, m))

def _get_drift_flag(detector) -> bool:
    # Works across multiple river versions
    if hasattr(detector, "drift_detected"):
        return bool(detector.drift_detected)
    if hasattr(detector, "change_detected"):
        return bool(detector.change_detected)
    return False

class DriftEngine:
    def __init__(self):
        self.adwin_hate_rate = ADWIN()
        self.adwin_jsd = ADWIN()
        self.hate_term_counters: dict[str, Counter] = {}

    def update(self, batch_no: str, hate_rate: float, hate_terms: list[str], baseline_batches: list[str]) -> dict:
        batch_no = str(batch_no)

        # 1) hate-rate drift
        self.adwin_hate_rate.update(float(hate_rate))
        hate_rate_drift = _get_drift_flag(self.adwin_hate_rate)

        # 2) term distribution drift
        cur = Counter(hate_terms)
        self.hate_term_counters[batch_no] = cur

        jsd_val = None
        jsd_drift = False

        if baseline_batches:
            base = Counter()
            for b in baseline_batches:
                base.update(self.hate_term_counters.get(str(b), Counter()))

            vocab = sorted(set(cur.keys()) | set(base.keys()))
            if vocab:
                p = _safe_prob(cur, vocab)
                q = _safe_prob(base, vocab)
                jsd_val = jsd(p, q)

                self.adwin_jsd.update(float(jsd_val))
                jsd_drift = _get_drift_flag(self.adwin_jsd)

        return {
            "batch_no": batch_no,
            "hate_rate": float(hate_rate),
            "hate_rate_drift": bool(hate_rate_drift),
            "jsd": jsd_val,
            "jsd_drift": bool(jsd_drift),
            "baseline_batches": list(map(str, baseline_batches)),
        }
