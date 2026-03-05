from collections import Counter, defaultdict

def term_label_stats(df_batch):
    """
    Returns:
      term_counts[t] = total occurrences of term t
      term_hate_counts[t] = occurrences where Hate=1
    """
    term_counts = Counter()
    term_hate_counts = Counter()

    for _, row in df_batch.iterrows():
        y = int(row["Hate"])
        for t in row["terms"]:
            t = str(t).strip()
            if not t:
                continue
            term_counts[t] += 1
            if y == 1:
                term_hate_counts[t] += 1
    return term_counts, term_hate_counts

def p_hate_given_term(term_counts, term_hate_counts, alpha=1.0):
    """
    Laplace smoothing:
      p = (hate + alpha) / (total + 2*alpha)
    """
    p = {}
    for t, n in term_counts.items():
        h = term_hate_counts.get(t, 0)
        p[t] = (h + alpha) / (n + 2*alpha)
    return p

def concept_proxy_drift(cur_p, base_p, min_support=3):
    """
    Computes:
      - mean_abs_delta over shared terms
      - fraction_terms_delta_gt_0.2
    """
    shared = set(cur_p.keys()) & set(base_p.keys())
    if not shared:
        return {"mean_abs_delta": None, "frac_delta_gt_0_2": None, "shared_terms": 0}

    deltas = [abs(cur_p[t] - base_p[t]) for t in shared]
    mean_abs = sum(deltas) / len(deltas)
    frac_big = sum(1 for d in deltas if d >= 0.2) / len(deltas)

    return {
        "mean_abs_delta": float(mean_abs),
        "frac_delta_gt_0_2": float(frac_big),
        "shared_terms": int(len(shared)),
    }
