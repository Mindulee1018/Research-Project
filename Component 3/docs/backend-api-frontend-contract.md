# Backend API Contract for Frontend

This document is the frontend-facing API contract for the current FastAPI backend.

## Base

- Local base URL: `http://127.0.0.1:5000`
- OpenAPI UI: `GET /docs`
- Response wrapper (default): `GenericResponse<T>`

```json
{
  "status_code": 200,
  "success": true,
  "message": "OK",
  "error_code": null,
  "data": {}
}
```

## Labels and Actions

- Labels: `HATE`, `DISINFO`, `NORMAL`
- Moderator actions: `approve`, `reject`, `escalate`, `rewrite`

## Endpoints

### 1) Moderate Text

- Method: `POST`
- Path: `/api/moderate`
- Request:

```json
{
  "text": "මේ ප්‍රවෘත්තිය හරිද කියලා තහවුරු කරලා බලන්න."
}
```

- Response `data` shape:

```json
{
  "original": "string",
  "cleaned": "string",
  "prediction": "HATE|DISINFO|NORMAL",
  "confidence": 0.0,
  "probs": {
    "HATE": 0.0,
    "DISINFO": 0.0,
    "NORMAL": 0.0
  },
  "harmful": true,
  "method": "SBERT Classifier"
}
```

### 2) Explanation + Suggestions (Primary)

- Method: `POST`
- Path: `/api/explain`
- Request:

```json
{
  "text": "ඔයාලා මේ ගැන ගොඩක් බොරු පතුරනවා කියලා හිතෙනවා.",
  "include_llm_feedback": false
}
```

- Response `data` shape:

```json
{
  "original": "string",
  "cleaned": "string",
  "prediction": "HATE|DISINFO|NORMAL",
  "probs": {},
  "xai_sentence": "string",
  "highlight_html": "string",
  "suggestions": [
    {
      "similarity": 0.0,
      "suggestion": "string",
      "matched_example": "string"
    }
  ],
  "llm_feedback": {
    "source": "gemini-vertex",
    "feedback": "string",
    "suggestions": ["string"],
    "caution": "string"
  },
  "method": "string",
  "error": null
}
```

Notes:
- `highlight_html` is ready to render as HTML.
- `llm_feedback` can be `null`.
- Set `include_llm_feedback=false` for interactive UI flows when low latency is more important than live Gemini feedback.
- Interactive UI flows may also use a lower LIME sample count on the backend for faster response time.
- Interactive UI flows may also use a lower SHAP evaluation budget on the backend for faster token-attribution response time.
- Legacy compatibility route: `/api/explain_lime` (same payload/response).

### 3) SHAP Token Contribution

- Method: `POST`
- Path: `/api/explain/shap`
- Request:

```json
{
  "text": "string",
  "include_llm_feedback": false
}
```

- Response `data` shape:

```json
{
  "original": "string",
  "cleaned": "string",
  "prediction": "HATE|DISINFO|NORMAL",
  "confidence": 0.0,
  "probs": {},
  "top_contributors": [
    {
      "token": "string",
      "contribution": 0.0,
      "direction": "supporting|opposing"
    }
  ],
  "method": "SHAP Text Explainer"
}
```

Notes:
- This endpoint is strict. If real SHAP is unavailable, the backend should return an explainability-unavailable error instead of fallback token weights.
- Interactive requests may use a reduced SHAP evaluation budget for faster UI response.

### 4) Counterfactual Explanations

- Method: `POST`
- Path: `/api/explain/counterfactual`
- Request:

```json
{
  "text": "string"
}
```

- Response `data` shape:

```json
{
  "original": "string",
  "original_prediction": "HATE|DISINFO|NORMAL",
  "original_confidence": 0.0,
  "counterfactuals": [
    {
      "text": "string",
      "prediction": "HATE|DISINFO|NORMAL",
      "confidence": 0.0,
      "changed": true,
      "score_delta": 0.0,
      "edit_summary": "string"
    }
  ],
  "method": "Counterfactual Candidate Search"
}
```

### 5) Attention Evidence

- Method: `POST`
- Path: `/api/explain/attention`
- Request:

```json
{
  "text": "string"
}
```

- Response `data` shape:

```json
{
  "original": "string",
  "cleaned": "string",
  "prediction": "HATE|DISINFO|NORMAL",
  "confidence": 0.0,
  "probs": {},
  "top_attention_tokens": [
    {
      "token": "string",
      "weight": 0.0
    }
  ],
  "note": "Attention is supporting evidence and not a standalone explanation.",
  "method": "sbert_transformer_attention (supporting evidence)"
}
```

Notes:
- This endpoint now returns encoder self-attention from the active model backend only.
- It should not silently substitute non-attention heuristics when strict attention evidence is unavailable.

### 6) Log Moderator Decision

- Method: `POST`
- Path: `/api/moderation/decision`
- Request:

```json
{
  "item_id": "yt_comment_1042",
  "source": "youtube",
  "text": "මෙහෙම කථා කියන්න එපා",
  "model_prediction": "HATE",
  "moderator_action": "rewrite",
  "final_label": "HATE",
  "moderator_id": "mod_01",
  "notes": "requested safer rewrite",
  "decided_at": "2026-03-16T12:00:00Z"
}
```

- Response: HTTP `201`, wrapper with:

```json
{
  "saved": true,
  "decision": {
    "decision_id": "uuid",
    "item_id": "string",
    "source": "string",
    "text": "string",
    "model_prediction": "string",
    "moderator_action": "string",
    "final_label": "string",
    "moderator_id": "string",
    "notes": "string",
    "decided_at": "iso",
    "logged_at": "iso"
  }
}
```

### 7) List Moderator Decisions

- Method: `GET`
- Path: `/api/moderation/decision`
- Query:
  - `limit` (optional, default `100`, min `1`, max `5000`)

- Response `data`:

```json
{
  "total": 0,
  "items": []
}
```

### 8) Export Moderator Decisions

- Method: `GET`
- Path: `/api/moderation/decision/export`
- Query:
  - `format` = `json` or `csv` (default `json`)

- Response `data`:

```json
{
  "format": "json",
  "total": 0,
  "content": "serialized-export-content"
}
```

### 9) Health

- Method: `GET`
- Path: `/health`
- Response `data`:

```json
{
  "status": "ok|degraded",
  "device": "cpu|cuda",
  "model_dir": "string",
  "classes": ["HATE", "DISINFO", "NORMAL"],
  "stopwords_enabled": true,
  "rewrite_index_ready": true,
  "embed_model": "string",
  "shap_enabled": true,
  "attention_enabled": true,
  "attention_backend": "sbert_transformer_attention",
  "llm_feedback_enabled": true,
  "llm_feedback_provider": "gemini-vertex"
}
```

## Frontend Integration Guidance

- For all wrapped endpoints:
  - check both HTTP status and `success`.
  - read payload from `data`.
- Use `/api/moderate` for queue/batch classification.
- Use `/api/explain` for main moderator explanation pane (reason + highlights + suggestions).
- Use `/api/explain/shap`, `/api/explain/counterfactual`, `/api/explain/attention` for advanced tabs.
- Persist moderator actions through `/api/moderation/decision`.

## Error Shape

Errors use same wrapper:

```json
{
  "status_code": 422,
  "success": false,
  "message": "Request validation failed.",
  "error_code": "VALIDATION_ERROR",
  "data": {
    "details": []
  }
}
```
