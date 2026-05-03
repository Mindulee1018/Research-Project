# Sinhala Harmful Content Annotation Guideline v1.0

Date: 2026-03-14

## Labels
- `HATE`: Content that attacks, dehumanizes, threatens, or promotes harm against a person/group identity (ethnicity, religion, nationality, gender, etc.).
- `DISINFO`: Verifiable false or misleading claim presented as fact, especially for public harm contexts (health, politics, safety, communal tension).
- `NORMAL`: Non-harmful, opinionated, neutral, or unclear content not meeting `HATE` or `DISINFO`.

## Priority Rule
When multiple categories appear in one comment:
1. Apply `HATE` if explicit targeted hatred/harm is present.
2. Else apply `DISINFO` if factual-claim misinformation is present.
3. Else `NORMAL`.

## Decision Rules
- Use only text in the comment row. Do not infer hidden intent from unknown context.
- Slurs + direct group targeting -> `HATE`.
- Calls for violence/exclusion against group/person identity -> `HATE`.
- Strong political opinion without a false factual claim -> `NORMAL`.
- Suspicious claim without enough evidence in text -> `NORMAL` unless clearly false and harmful.
- Satire/jokes: label by literal harmful impact and explicitness in text.

## Borderline Tie-Breaks
- Insults toward an individual without identity-based targeting -> `NORMAL` unless explicit threat.
- Rumor-like claims ("someone said...") without assertive fact framing -> `NORMAL`.
- Edited/rewritten quote with clear correction/disclaimer -> `NORMAL`.
- If two annotators disagree between `DISINFO` and `NORMAL`, escalate to adjudication queue.

## Annotation Workflow
1. Primary annotator assigns label and keeps `annotation_status=pending` -> `labeled`.
2. Secondary annotator reviews disagreement subset.
3. Adjudicator resolves conflicts and sets final label.
4. Any unreadable/noise rows should be flagged for exclusion in adjudication.

## Required Output Fields
- `candidate_id`
- `snapshot_id`
- `source`
- `source_item_id_or_url`
- `scraped_at`
- `text`
- `label`
- `annotation_status`
