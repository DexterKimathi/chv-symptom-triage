# CHV Symptom Triage: Frontend

**Student:** Dexter Kimathi (166889) · **Group:** U-CS 31

Mobile-first website for community health volunteers. A volunteer logs in, answers 35
yes/no symptom questions for a patient, and gets referral guidance with the most likely
illness. It runs in the phone's browser, so there is nothing to install.

Stack: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4.

## Repos

- Frontend: https://github.com/RAM-AS-RAP/ucs31-kimathi-frontend (this repo)
- Backend: https://github.com/RAM-AS-RAP/ucs31-kimathi-backend
- ML: https://github.com/RAM-AS-RAP/ucs31-kimathi-ml

## Run

```
npm install
cp .env.example .env.local
npm run dev
```

Opens on http://localhost:3000. The backend must be running on port 8000 (see the backend
README). Demo logins come from the backend's `scripts/seed.py`.

Production build: `npm run build && npm start`. Lint: `npm run lint`.

## Screens

| Path | Who | What |
|---|---|---|
| `/login` | everyone | Phone number and password |
| `/` | logged in | Start an assessment, list of recent ones |
| `/assess` | logged in | Patient code, age and sex, then the questions in 7 short steps, danger signs first |
| `/history/[id]` | logged in | The result: urgent banner if needed, what to do, other possibilities, the answers behind it, disclaimer |
| `/admin` | admins | Create volunteer and admin accounts |

Logged-out visitors are sent to `/login`. `/admin` is hidden from volunteers in the app, and
the backend refuses admin calls from non-admin tokens (403), so the real check is on the server.

## Code layout

- `src/lib/api.ts`: every backend call. The base URL comes from `NEXT_PUBLIC_API_BASE_URL`.
- `src/lib/types.ts`: response shapes, kept in step with the backend's `docs/api.md`.
- `src/lib/auth.tsx`: login state (kept in localStorage), the `RequireAuth` page guard, and
  logout on an expired token.
- `src/components/`: shared building blocks and the result layout.
- `src/app/`: one folder per screen.

## Notes

Volunteers use low-cost phones on mobile data, so pages stay light: no heavy images, and
only the scripts each page needs.

Every result screen shows a disclaimer and a seek-professional-care message, with referral
guidance as the most prominent element. A result is never presented as a diagnosis.
