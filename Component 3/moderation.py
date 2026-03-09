def get_moderation_decision(prediction: str, probs: dict) -> dict:
    """
    Convert model prediction + probabilities into a moderation action.
    Classes in your model: HATE, DISINFO, NORMAL
    """

    top_score = float(probs.get(prediction, 0.0))

    # default response
    decision = {
        "action": "ALLOW",
        "severity": "LOW",
        "reason": "Content appears safe.",
        "confidence": round(top_score, 4)
    }

    if prediction == "HATE":
        if top_score >= 0.85:
            decision = {
                "action": "BLOCK",
                "severity": "HIGH",
                "reason": "High-confidence hateful or abusive content detected.",
                "confidence": round(top_score, 4)
            }
        elif top_score >= 0.60:
            decision = {
                "action": "REVIEW",
                "severity": "MEDIUM",
                "reason": "Potential hateful content detected. Needs moderation review.",
                "confidence": round(top_score, 4)
            }
        else:
            decision = {
                "action": "WARN",
                "severity": "MEDIUM",
                "reason": "Low-confidence hateful content signal detected.",
                "confidence": round(top_score, 4)
            }

    elif prediction == "DISINFO":
        if top_score >= 0.85:
            decision = {
                "action": "FLAG",
                "severity": "HIGH",
                "reason": "High-confidence misleading or false information detected.",
                "confidence": round(top_score, 4)
            }
        elif top_score >= 0.60:
            decision = {
                "action": "REVIEW",
                "severity": "MEDIUM",
                "reason": "Possible misinformation detected. Needs verification.",
                "confidence": round(top_score, 4)
            }
        else:
            decision = {
                "action": "WARN",
                "severity": "LOW",
                "reason": "Weak misinformation signal detected.",
                "confidence": round(top_score, 4)
            }

    elif prediction == "NORMAL":
        if top_score >= 0.70:
            decision = {
                "action": "ALLOW",
                "severity": "LOW",
                "reason": "Safe content.",
                "confidence": round(top_score, 4)
            }
        else:
            decision = {
                "action": "ALLOW_WITH_LOG",
                "severity": "LOW",
                "reason": "Mostly safe, but confidence is not very strong.",
                "confidence": round(top_score, 4)
            }

    return decision