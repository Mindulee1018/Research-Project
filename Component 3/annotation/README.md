# Annotation

Contains annotation assets and quality workflows:

- `guidelines/` for label policy (`HATE`, `DISINFO`, `NORMAL`)
- `adjudication/` for disagreement resolution and agreement reports

Store guideline versions explicitly so every dataset release can reference them.

Current baseline guideline:

- `guidelines/label-guideline-v1.0.md`

Dual-annotation workflow:

- Prepare workflow assets (master, hard examples, annotator A/B sheets):
  - `./scripts/run-prepare-annotation-workflow.ps1`
- Auto-label one annotator sheet with Gemini (Vertex AI, resumable):
  - `./scripts/run-auto-label-gemini.ps1`
- Relabel model error cases with Gemini adjudication (resumable):
  - `./scripts/run-gemini-error-relabel.ps1`
- Apply approved error-case relabels back into the master labeled sheet:
  - `./scripts/run-apply-error-relabels.ps1`
- Merge a new labeled CSV into the master labeled sheet:
  - `./scripts/run-merge-labeled-csvs.ps1`
- Merge two completed annotator sheets and generate adjudication queue:
  - `./scripts/run-merge-dual-annotations.ps1`

Auto-label outputs:

- Labeled sheet (default): `annotation/workflow/current/annotator_a_llm.csv`
- Resume state: `annotation/workflow/state/gemini_label_state.json`
- Last run summary: `annotation/workflow/state/gemini_label_report.json`
- Harmful-label trigger terms: `llm_cause_words` (for `HATE`/`DISINFO`)
