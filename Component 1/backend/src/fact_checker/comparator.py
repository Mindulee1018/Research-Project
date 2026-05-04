# comparator.py
# Compares YouTube comments against MULTIPLE news sources
# Takes average similarity → stronger conclusion

from sentence_transformers import SentenceTransformer, util

SBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# ── Thresholds ─────────────────────────────────────────────────
DISINFO_HIGH   = 0.25   # avg similarity < 0.25 → HIGH confidence DISINFO
DISINFO_LOW    = 0.40   # avg similarity < 0.40 → MODERATE confidence DISINFO
NOT_DISINFO    = 0.60   # avg similarity > 0.60 → NOT DISINFO
# Between 0.40 and 0.60 → UNCERTAIN


class FactChecker:
    def __init__(self):
        print("Loading Sentence-BERT model for fact checking...")
        self.model = SentenceTransformer(SBERT_MODEL)
        print("✅ FactChecker ready!")

    def get_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        if not text1 or not text2:
            return 0.5
        try:
            emb1 = self.model.encode(text1, convert_to_tensor=True)
            emb2 = self.model.encode(text2, convert_to_tensor=True)
            return round(float(util.cos_sim(emb1, emb2)[0][0]), 4)
        except Exception:
            return 0.5

    def check_comment(self, comment: str, news_articles: list) -> dict:
        """
        Compare comment against MULTIPLE news articles.
        - Computes similarity against each article
        - Takes AVERAGE similarity across all sources
        - Verdict based on average → stronger conclusion

        Returns verdict, per-source breakdown, average similarity, explanation
        """
        if not news_articles:
            return {
                "verdict":      "UNVERIFIED",
                "confidence":   "No articles found",
                "avg_similarity": 0.0,
                "source_scores":  [],
                "best_match":   None,
                "explanation":  "No news articles found to compare against",
            }

        source_scores  = []
        best_similarity = 0.0
        best_article   = None

        # ── Compare against each article ──────────────────────
        for article in news_articles:
            news_text  = f"{article.get('title', '')} {article.get('snippet', '')} {article.get('content', '')}"
            similarity = self.get_similarity(comment, news_text)

            source_scores.append({
                "source":     article.get("source", "Unknown"),
                "title":      article.get("title", ""),
                "url":        article.get("url", ""),
                "similarity": similarity,
            })

            if similarity > best_similarity:
                best_similarity = similarity
                best_article    = article

        # ── Calculate average similarity ──────────────────────
        avg_similarity = round(
            sum(s["similarity"] for s in source_scores) / len(source_scores), 4
        )

        # Sort source scores high to low
        source_scores.sort(key=lambda x: x["similarity"], reverse=True)

        # Count how many sources agree on DISINFO
        disinfo_sources    = [s for s in source_scores if s["similarity"] < DISINFO_LOW]
        not_disinfo_sources = [s for s in source_scores if s["similarity"] > NOT_DISINFO]

        print(f"   Comment similarity scores: avg={avg_similarity} | "
              f"disinfo_sources={len(disinfo_sources)} | "
              f"not_disinfo_sources={len(not_disinfo_sources)}")

        # ── Verdict based on AVERAGE similarity ───────────────
        if avg_similarity < DISINFO_HIGH:
            verdict     = "DISINFO"
            confidence  = "High Confidence"
            explanation = (
                f"Comment strongly contradicts news across {len(source_scores)} sources "
                f"(avg similarity={avg_similarity:.2f}). "
                f"{len(disinfo_sources)}/{len(source_scores)} sources show low alignment."
            )

        elif avg_similarity < DISINFO_LOW:
            verdict     = "DISINFO"
            confidence  = "Moderate Confidence"
            explanation = (
                f"Comment likely contradicts news "
                f"(avg similarity={avg_similarity:.2f} across {len(source_scores)} sources). "
                f"{len(disinfo_sources)}/{len(source_scores)} sources show low alignment."
            )

        elif avg_similarity > NOT_DISINFO:
            verdict     = "NOT DISINFO"
            confidence  = "High Confidence"
            explanation = (
                f"Comment aligns well with news across {len(source_scores)} sources "
                f"(avg similarity={avg_similarity:.2f}). "
                f"{len(not_disinfo_sources)}/{len(source_scores)} sources confirm alignment."
            )

        else:
            verdict     = "UNCERTAIN"
            confidence  = "Low Confidence"
            explanation = (
                f"Could not conclusively verify this claim "
                f"(avg similarity={avg_similarity:.2f} across {len(source_scores)} sources). "
                f"Manual review recommended."
            )

        return {
            "verdict":        verdict,
            "confidence":     confidence,
            "avg_similarity": avg_similarity,
            "source_scores":  source_scores,
            "best_match":     best_article,
            "explanation":    explanation,
        }

    def check_batch(self, comments: list, news_articles: list) -> list:
        """Check multiple comments against same set of news articles."""
        results = []
        for comment in comments:
            result          = self.check_comment(comment, news_articles)
            result["comment"] = comment
            results.append(result)
        return results