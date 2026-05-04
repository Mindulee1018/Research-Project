# nli_fact_checker.py
# NLI-based fact checking — FEVER methodology
# Per-source verdicts + final majority verdict
#
# Logic:
# Both SUPPORT     → NOT DISINFO (strong)
# Both REFUTE      → DISINFO  (strong)
# One found, one not → show what found + UNCERTAIN 
# One SUPPORT one REFUTE → UNCERTAIN 
# Neither found    → UNVERIFIED

from transformers import pipeline

ENTAILMENT    = "entailment"
CONTRADICTION = "contradiction"
NEUTRAL       = "neutral"


class NLIFactChecker:
    def __init__(self):
        print("Loading NLI model (nli-MiniLM2 — 90MB fast CPU model)...")
        self.nli = pipeline(
            "zero-shot-classification",
            model="cross-encoder/nli-MiniLM2-L6-H768",
            device=-1,
        )
        print("NLI FactChecker ready!")

    def check_claim_against_evidence(self, claim: str, evidence: str) -> dict:
        """Run NLI between claim and a single evidence text."""
        if not claim or not evidence:
            return {"label": NEUTRAL, "verdict": "UNCERTAIN", "score": 0.0}
        try:
            result = self.nli(
                sequences=evidence[:500],
                candidate_labels=[
                    f"This confirms: {claim[:100]}",
                    f"This contradicts: {claim[:100]}",
                    f"This is unrelated to: {claim[:100]}",
                ],
            )
            labels = result["labels"]
            scores = result["scores"]
            top    = labels[scores.index(max(scores))]

            if "confirms" in top:
                return {"label": ENTAILMENT,    "verdict": "NOT DISINFO", "score": round(max(scores), 4)}
            elif "contradicts" in top:
                return {"label": CONTRADICTION, "verdict": "DISINFO",     "score": round(max(scores), 4)}
            else:
                return {"label": NEUTRAL,       "verdict": "UNCERTAIN",   "score": round(max(scores), 4)}
        except Exception as e:
            print(f"⚠️ NLI error: {e}")
            return {"label": NEUTRAL, "verdict": "UNCERTAIN", "score": 0.0}

    def check_per_source(self, claim: str, source_results: dict) -> dict:
        """
        Check claim against each source independently.
        source_results: { source_name: [articles] }

        Returns per-source verdicts + final verdict.

        Final verdict logic:
        - Both SUPPORT     → NOT DISINFO 
        - Both REFUTE      → DISINFO 
        - One found result, other didn't → UNCERTAIN ⚠️ (show what found)
        - One SUPPORT one REFUTE → UNCERTAIN ⚠️
        - No source found anything → UNVERIFIED
        """
        per_source = {}

        for source_name, articles in source_results.items():

            # ── No articles found for this source ──────────────
            if not articles:
                per_source[source_name] = {
                    "verdict":      "NO ARTICLES",
                    "articles":     [],
                    "entail":       0,
                    "contradict":   0,
                    "neutral":      0,
                    "top_article":  None,
                    "explanation":  f"No relevant articles found on {source_name}",
                }
                continue

            # ── Run NLI against each article ───────────────────
            article_results = []
            entail_count    = 0
            contradict_count = 0
            neutral_count   = 0
            best_score      = 0.0
            best_article    = None

            for article in articles:
                evidence = f"{article.get('title','')} {article.get('content','')}".strip()
                if not evidence:
                    continue

                nli_result = self.check_claim_against_evidence(claim, evidence)

                article_results.append({
                    "title":   article.get("title", ""),
                    "url":     article.get("url", ""),
                    "label":   nli_result["label"],
                    "verdict": nli_result["verdict"],
                    "score":   nli_result["score"],
                })

                if nli_result["label"] == ENTAILMENT:
                    entail_count += 1
                elif nli_result["label"] == CONTRADICTION:
                    contradict_count += 1
                else:
                    neutral_count += 1

                if nli_result["score"] > best_score:
                    best_score   = nli_result["score"]
                    best_article = article_results[-1]

            # ── Source-level verdict ───────────────────────────
            total = len(article_results)
            if entail_count > contradict_count and entail_count > neutral_count:
                source_verdict = "NOT DISINFO"
                explanation    = f"{entail_count}/{total} articles SUPPORT this claim"
            elif contradict_count > entail_count and contradict_count > neutral_count:
                source_verdict = "DISINFO"
                explanation    = f"{contradict_count}/{total} articles REFUTE this claim"
            else:
                source_verdict = "UNCERTAIN"
                explanation    = f"Mixed results ({total} articles)"

            per_source[source_name] = {
                "verdict":      source_verdict,
                "articles":     article_results,
                "entail":       entail_count,
                "contradict":   contradict_count,
                "neutral":      neutral_count,
                "top_article":  best_article,
                "explanation":  explanation,
            }

        # ── Final verdict across all sources ───────────────────
        sources_with_articles = {
            k: v for k, v in per_source.items()
            if v["verdict"] != "NO ARTICLES"
        }
        sources_not_found = {
            k: v for k, v in per_source.items()
            if v["verdict"] == "NO ARTICLES"
        }

        source_verdicts = [v["verdict"] for v in sources_with_articles.values()]

        if not sources_with_articles:
            # No source found anything
            final_verdict    = "UNVERIFIED"
            final_confidence = "No articles found on any source"
            final_explanation = "Could not find relevant news articles on any news site."

        elif len(sources_with_articles) == 1:
            # Only one source found articles
            found_source   = list(sources_with_articles.keys())[0]
            found_verdict  = source_verdicts[0]
            missing_source = list(sources_not_found.keys())

            if found_verdict == "NOT DISINFO":
                final_verdict     = "UNCERTAIN"
                final_confidence  = f"Only {found_source} found articles — {found_verdict}"
                final_explanation = (
                    f"{found_source} suggests this is NOT DISINFO, but "
                    f"{', '.join(missing_source)} found no relevant articles. "
                    f"Cannot confirm conclusively."
                )
            elif found_verdict == "DISINFO":
                final_verdict     = "UNCERTAIN"
                final_confidence  = f"Only {found_source} found articles — {found_verdict}"
                final_explanation = (
                    f"{found_source} suggests this may be DISINFO, but "
                    f"{', '.join(missing_source)} found no relevant articles. "
                    f"Cannot confirm conclusively."
                )
            else:
                final_verdict     = "UNCERTAIN"
                final_confidence  = f"Only {found_source} found articles"
                final_explanation = f"Inconclusive results from {found_source} only."

        elif all(v == "NOT DISINFO" for v in source_verdicts):
            final_verdict     = "NOT DISINFO"
            final_confidence  = f"All {len(sources_with_articles)} sources SUPPORT this claim"
            final_explanation = "Multiple reliable sources confirm this claim is accurate."

        elif all(v == "DISINFO" for v in source_verdicts):
            final_verdict     = "DISINFO"
            final_confidence  = f"All {len(sources_with_articles)} sources REFUTE this claim"
            final_explanation = "Multiple reliable sources contradict this claim — likely disinformation."

        else:
            final_verdict     = "UNCERTAIN"
            final_confidence  = "Sources disagree"
            final_explanation = (
                f"Sources give conflicting verdicts: "
                + ", ".join(f"{k}={v['verdict']}" for k, v in sources_with_articles.items())
            )

        return {
            "final_verdict":    final_verdict,
            "final_confidence": final_confidence,
            "final_explanation": final_explanation,
            "per_source":       per_source,
        }