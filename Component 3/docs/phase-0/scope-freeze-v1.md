# Phase 0: Scope Freeze (v1)

## Objective
Deliver a requirement-aligned moderation system for harmful Sinhala content with transparent explanations and moderator decision support.

## In Scope (v1)
- Sentence-BERT-centered model for `HATE`, `DISINFO`, `NORMAL`.
- Explainability stack: SHAP + counterfactuals + supporting attention evidence.
- FastAPI backend with structured endpoints for moderation and explanations.
- Next.js moderator dashboard with single + batch review.
- Harmful-content rewrite suggestions in moderator workflow.
- Decision logging for user-study and moderation analysis.
- Data ingestion pipeline for required sources: YouTube, Gossip Lanka, Elakiri.
- Annotation and evaluation workflow with reproducible data/model versioning.

## Out of Scope (v1)
- Full production MLOps platform and autoscaling infrastructure.
- Real-time social network graph-risk scoring beyond the moderation component.
- Multi-language moderation beyond Sinhala-focused behavior.
- Database-heavy analytics warehouse and enterprise BI integration.
- Mobile app clients.

## Non-Goals
- Shipping a generic chatbot.
- Treating attention visualization as standalone explanation truth.
- Using legacy synthetic datasets as final authoritative research evidence.
- Expanding feature set before meeting mandatory requirement coverage.

## Working Assumptions
- Existing repository is a baseline reference and controlled migration source.
- DB integration is not required for this stage unless scope changes.
- Thresholds in acceptance criteria are draft defaults pending sign-off.
- Attention evidence must be described honestly as supporting model-attention output unless a separate literal AllenNLP-native integration path is implemented and validated.

## Sign-Off Checklist
- [ ] Requirement matrix approved (`requirements-traceability-matrix.md`)
- [ ] Acceptance criteria approved (`acceptance-criteria-v1.md`)
- [ ] In-scope and out-of-scope approved
- [ ] Default metric/quality thresholds approved or updated
- [ ] Phase 1 kickoff authorized

## Sign-Off Record
- Date:
- Approved by:
- Notes:
