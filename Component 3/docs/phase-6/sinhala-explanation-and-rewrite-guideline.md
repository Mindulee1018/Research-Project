# Sinhala Explanation and Rewrite Guideline

## Purpose

This guideline defines how explanation text and rewrite suggestions should be judged for the moderator-facing application. It exists to support the requirement that explanations and remediation guidance must be understandable, culturally appropriate, and aligned with Sinhala moderation use cases.

This artifact is not a model-training rulebook. It is a review and quality-check guide for:

- explanation sentences shown to moderators
- harmful-word evidence displays
- rewrite or safer-phrasing suggestions
- LLM-generated moderation feedback

## Scope

Applies to outputs associated with these labels:

- `HATE`
- `DISINFO`
- `NORMAL`

Applies to these backend/frontend flows:

- `POST /api/explain`
- `POST /api/explain/shap`
- `POST /api/explain/counterfactual`
- moderator console explanation and what-if UI

## Core Principles

### 1. Use moderator-facing Sinhala, not academic jargon

Explanation text should be understandable by a moderator making a quick review decision. It should not read like a model-debugging log or a research note.

Good pattern:
- explain what triggered the flag
- explain whether it is targeted abuse, harmful accusation, or misleading factual content
- keep wording direct and short

Avoid:
- long technical descriptions
- internal model language
- unclear English-heavy phrasing

### 2. Do not overclaim certainty

The explanation must not state that the comment is definitely false, definitely criminal, or definitely hateful unless the text itself clearly supports that claim.

Preferred phrasing:
- “this comment appears to spread an unverified claim”
- “this text contains targeted insulting language”
- “this wording may encourage harmful interpretation”

Avoid:
- “this is 100% false”
- “the person is guilty”
- “the writer is definitely spreading lies”

### 3. Ground explanations in visible text evidence

If a comment is flagged as `HATE` or `DISINFO`, the explanation should be defensible from words or short phrases present in the comment.

Expected evidence behavior:
- highlight specific harmful words or short phrases
- keep evidence tied to the displayed text
- avoid unsupported assumptions about hidden context

### 4. Keep Sinhala social-media context in mind

Review should consider:
- colloquial Sinhala insults
- mocking or humiliating phrasing
- rumor-style statements presented as fact
- strong emotional language that is not necessarily hate
- sarcasm or casual slang that may look harmful but is not clearly targeted

This matters especially for:
- `HATE` vs `NORMAL`
- `DISINFO` vs emotional opinion or suspicion

### 5. Rewrite suggestions must preserve intent while reducing harm

A rewrite should not merely delete meaning. It should:
- reduce abuse
- reduce incitement
- reduce certainty of unverified factual claims
- preserve the core message where possible

For `HATE`:
- move from insult/attack to neutral criticism
- remove humiliating or dehumanizing expressions

For `DISINFO`:
- move from asserted rumor to cautious or verification-oriented wording
- encourage checking or verifying before sharing

## Label-Specific Review Rules

### HATE

The output is acceptable when it clearly points to:
- targeted insult
- demeaning phrasing
- directed harassment
- humiliation or attack against a person or group

The output is weak when:
- profanity alone is treated as hate
- frustration or anger is flagged without a target
- criticism is explained as hate without evidence of attack

### DISINFO

The output is acceptable when it clearly points to:
- likely false or unverified claim stated as fact
- rumor-spreading language
- encouragement to share an unverified claim
- misleading certainty around factual content

The output is weak when:
- ordinary suspicion is treated as disinformation
- questions are treated as false claims
- criticism or disbelief is treated as rumor-spreading without evidence

### NORMAL

The output is acceptable when it makes clear that:
- the text is non-harmful
- there is no clear targeted abuse
- there is no clear misinformation signal strong enough to flag

The output is weak when:
- it ignores obvious abuse
- it ignores obvious rumor-style certainty
- it explains normality with generic filler rather than text-specific reasoning

## Rewrite Quality Checklist

Use this checklist when reviewing suggestions:

- The rewrite is in understandable Sinhala.
- The rewrite removes the strongest harmful trigger words.
- The rewrite does not introduce new factual claims.
- The rewrite does not change the topic completely.
- The rewrite still sounds natural for moderator guidance.
- The rewrite is shorter or equally concise where possible.

## Explanation Quality Checklist

Mark an explanation as acceptable only if all are true:

- The label matches the visible text.
- The reason is understandable without technical knowledge.
- The wording does not overclaim certainty.
- The explanation uses text evidence, not guesswork.
- The suggested rewrite is safer and still meaningful.

## Sample Review Template

Use this small manual-review template when sampling explanations:

| Item ID | Predicted Label | Explanation Clear | Evidence Grounded | Sinhala Natural | Rewrite Useful | Notes |
|---|---|---|---|---|---|---|
| example_001 | HATE | yes/no | yes/no | yes/no | yes/no | short comment |

Recommended sample size for report evidence:

- at least 20 moderator-facing outputs
- include all three labels
- include both successful and borderline examples

## Current Application Interpretation

For the current application build:

- SHAP token evidence should be treated as supporting evidence, not the full explanation
- counterfactual and rewrite suggestions should be reviewed with this guideline
- the moderator what-if flow should be judged by whether it helps a human understand how wording changes alter the model output

## Intended Evidence Use

This guideline can be referenced in:

- methodology/report sections about culturally contextual explanation quality
- frontend evaluation notes
- moderator usability/trust study preparation
- requirement traceability for `X-05`
