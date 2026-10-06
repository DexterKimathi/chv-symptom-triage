# CHV Symptom Triage: Frontend

**Student:** Dexter Kimathi (166889) · **Group:** U-CS 31

Mobile-first website for community health volunteers. A volunteer logs in, answers 35
yes/no symptom questions for a patient, and gets referral guidance with the most likely
illness. It runs in the phone's browser, so there is nothing to install.

Stack: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4. Visual design: the CHV
Triage design system (Atkinson Hyperlegible type, tokens in `src/app/globals.css`).

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
| `/` | logged in | Volunteer name, start an assessment, recent assessments |
| `/assess` | logged in | Patient code, age and sex, then 35 questions in 7 pages of 5. Next unlocks when all 5 are answered |
| `/result/[id]` | logged in | The result straight after sending |
| `/history/[id]` | logged in | A past result, read-only, exactly as first shown |
| `/admin` | admins | Add a volunteer account |

Every result follows the same order: what was found, what to do (the largest block, coloured
by referral level), supporting detail, then the disclaimer. Red is used only for urgent referral.

Answers are saved on the phone while the assessment is in progress, so a dropped connection
never means asking the patient again. They are cleared once the result is saved, or on Cancel.

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
