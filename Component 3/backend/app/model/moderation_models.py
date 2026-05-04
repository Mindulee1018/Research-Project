from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    text: str = Field(default="")
    include_llm_feedback: bool = Field(
        default=True,
        description="When false, skip live Gemini feedback generation to reduce interactive latency.",
    )
    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "ඔයාලා මේ ගැන ගොඩක් බොරු පතුරනවා කියලා හිතෙනවා.",
                "include_llm_feedback": True,
            }
        }
    }


class ModerateRequest(BaseModel):
    text: str = Field(default="")
    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "මේ ප්‍රවෘත්තිය හරිද කියලා තහවුරු කරලා බලන්න."
            }
        }
    }


class RewriteSuggestion(BaseModel):
    similarity: float
    suggestion: str
    matched_example: str


class LlmModerationFeedback(BaseModel):
    source: str = Field(default="gemini")
    feedback: str
    suggestions: List[str] = Field(default_factory=list)
    caution: Optional[str] = None


class ExplainResult(BaseModel):
    original: str
    cleaned: str
    prediction: str
    probs: Dict[str, float]
    xai_sentence: str
    highlight_html: str
    suggestions: List[RewriteSuggestion] = Field(default_factory=list)
    llm_feedback: Optional[LlmModerationFeedback] = None
    method: Optional[str] = None
    error: Optional[str] = None


class LlmFeedbackResult(BaseModel):
    original: str
    cleaned: str
    prediction: str
    probs: Dict[str, float]
    suggestions: List[RewriteSuggestion] = Field(default_factory=list)
    llm_feedback: Optional[LlmModerationFeedback] = None
    method: Optional[str] = None


class ModerateResult(BaseModel):
    original: str
    cleaned: str
    prediction: str
    confidence: float
    probs: Dict[str, float]
    harmful: bool
    method: str = "SBERT Classifier"


class TokenContribution(BaseModel):
    token: str
    contribution: float
    direction: str


class ShapExplainResult(BaseModel):
    original: str
    cleaned: str
    prediction: str
    confidence: float
    probs: Dict[str, float]
    top_contributors: List[TokenContribution] = Field(default_factory=list)
    method: str = "SHAP Text Explainer"


class CounterfactualCandidate(BaseModel):
    text: str
    prediction: str
    confidence: float
    changed: bool
    score_delta: float
    edit_summary: str


class CounterfactualExplainResult(BaseModel):
    original: str
    original_prediction: str
    original_confidence: float
    counterfactuals: List[CounterfactualCandidate] = Field(default_factory=list)
    method: str = "Counterfactual Candidate Search"


class AttentionWeight(BaseModel):
    token: str
    weight: float


class AttentionExplainResult(BaseModel):
    original: str
    cleaned: str
    prediction: str
    confidence: float
    probs: Dict[str, float]
    top_attention_tokens: List[AttentionWeight] = Field(default_factory=list)
    note: str = "Attention is supporting evidence and not a standalone explanation."
    method: str = "Encoder Self-Attention (Supporting)"


class HealthResult(BaseModel):
    status: str
    device: str
    model_dir: str
    classes: List[str]
    stopwords_enabled: bool
    rewrite_index_ready: bool
    embed_model: str
    shap_enabled: bool = False
    attention_enabled: bool = False
    attention_backend: Optional[str] = None
    llm_feedback_enabled: bool = False
    llm_feedback_provider: Optional[str] = None


class DecisionLogRequest(BaseModel):
    item_id: str = Field(default="", description="UI item/comment identifier.")
    source: str = Field(default="", description="Source name such as youtube/gossip_lanka/elakiri.")
    text: str = Field(default="", description="Moderated text.")
    model_prediction: str = Field(default="", description="Model class before moderator override.")
    moderator_action: Literal["approve", "reject", "escalate", "rewrite"] = Field(default="approve")
    final_label: Literal["HATE", "DISINFO", "NORMAL"] = Field(default="NORMAL")
    moderator_id: str = Field(default="anonymous")
    notes: str = Field(default="")
    decided_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp.",
    )
    model_config = {
        "json_schema_extra": {
            "example": {
                "item_id": "yt_comment_1042",
                "source": "youtube",
                "text": "මෙහෙම කථා කියන්න එපා",
                "model_prediction": "HATE",
                "moderator_action": "rewrite",
                "final_label": "HATE",
                "moderator_id": "mod_01",
                "notes": "requested safer rewrite",
            }
        }
    }


class DecisionLogItem(BaseModel):
    decision_id: str
    item_id: str
    source: str
    text: str
    model_prediction: str
    moderator_action: str
    final_label: str
    moderator_id: str
    notes: str
    decided_at: str
    logged_at: str


class DecisionLogCreateResult(BaseModel):
    saved: bool = True
    decision: DecisionLogItem


class DecisionLogListResult(BaseModel):
    total: int
    items: List[DecisionLogItem] = Field(default_factory=list)


class DecisionLogExportResult(BaseModel):
    format: Literal["json", "csv"]
    total: int
    content: str


class DecisionLogClearResult(BaseModel):
    cleared: bool = True
    removed: int = 0
