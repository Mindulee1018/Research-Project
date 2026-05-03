# Frontend (Next.js)

This frontend uses Next.js App Router and React.

## Run

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

Routes:

- `/` overview console
- `/moderate` single moderation focus
- `/batch` batch queue focus
- `/decisions` decision-log focus

## Build

```bash
npm run build
npm run start
```

## Environment

Create `frontend/.env.local` from `frontend/.env.example`.

PowerShell:

```bash
Copy-Item .env.example .env.local
```

Supported variables:

```bash
NEXT_PUBLIC_API_BASE=http://127.0.0.1:5000
NEXT_PUBLIC_MODERATOR_ID=ui_moderator
```

Notes:
- `NEXT_PUBLIC_API_BASE` should point to the FastAPI backend.
- If omitted, frontend defaults to `http://127.0.0.1:5000`.
- Queue/progress state is stored in browser `localStorage` and recovers on refresh.
