# AGENTS.md

This file governs the entire repository rooted at `D:\Desktop\Projects\client\sl-social-media-risk-analysis`.

## Project Purpose

This repository is the clean implementation base for:

- Project: `AI For Harmful Content Detection And Network Risk Analysis In Sri Lankan Social Media`
- Focused component: transparent moderation of harmful Sinhala content with interpretable AI

This repository replaces an older prototype. Treat migrated files as baseline reference code, not final architecture.

## Repository Structure

Keep work organized under these top-level areas:

- `data/`
  - `datasets/legacy/`: migrated prototype/reference datasets
  - `rewrites/`: rewrite suggestion source data
- `training/`
  - model training scripts
  - preprocessing and experiment utilities
  - generated artifacts under `training/artifacts/`
- `backend/`
  - moderation API
  - explanation endpoints
  - backend templates only if still needed
- `frontend/`
  - moderator dashboard and explanation UI

When creating new code, prefer extending this structure instead of adding ad hoc files at repo root.

## Coding Guidance

- Treat the current Python and frontend code as `legacy baseline`.
- Prefer incremental cleanup over copying more files from the old repository.
- Do not commit or rely on `frontend/node_modules`, `frontend/dist`, or generated training artifacts.
- Keep paths relative to this repository, not the old prototype repository.
- If training or backend code depends on datasets or artifact locations, keep those paths explicit and centralized.

## NotebookLM MCP

This project has an associated NotebookLM notebook and it should be used when the task involves project planning, requirements capture, implementation notes, migration notes, or research summaries.

Notebook details:

- Notebook title: `sl-social-media-risk-analysis`
- Notebook ID: `3b8cbc99-daab-471d-91a2-c1095991049a`

Expected usage:

- Use NotebookLM MCP when asked to store project notes, assessments, plans, architecture notes, or research summaries.
- Prefer adding concise, structured documents instead of fragmented notes.
- When a task produces a meaningful decision record, implementation plan, or evaluation summary, consider updating the notebook.
- Do not use NotebookLM as a substitute for reading the actual repository files when code-level accuracy matters.

## Migration Context

Important repository context:

- The previous prototype had usable pieces for:
  - baseline classifier training
  - Flask inference API
  - React moderation demo UI
  - LIME explanations
  - rewrite suggestions
- The previous prototype did not fully satisfy the final project requirements.
- New work should move toward:
  - cleaner architecture
  - stronger data pipeline
  - explainability methods aligned with the actual project scope
  - maintainable backend/frontend separation

## Preferred Working Style

- Before major refactors, inspect the existing structure and identify whether code is `legacy baseline`, `migrated asset`, or `new implementation`.
- Prefer creating or updating small focused docs when major architectural decisions are made.
- If a change affects project direction, assumptions, or implementation scope, keep the notebook and repository docs aligned.

## Research Reporting Workflow

- For data-pipeline and training workflow changes, maintain an `.ipynb` notebook version under `notebooks/` so steps are report-ready.
- Prefer keeping notebook pipelines executable end-to-end with explicit commands and artifact paths.
- When implementing multi-step work, record each meaningful step as structured notes in the project NotebookLM notebook (`3b8cbc99-daab-471d-91a2-c1095991049a`).
