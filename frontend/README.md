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

Production build: `npm run build && npm start`. The build stops with an error if
`NEXT_PUBLIC_API_BASE_URL` is not set (in `.env.local`, `.env.production` or the shell),
because the backend address is written into the app at build time. `npm run dev` falls back
to http://localhost:8000.

Checks: `npm run lint`, then `npx next typegen && npx tsc --noEmit`. Run `next typegen` (or
`npm run build`) first: `tsc` alone reports `Cannot find name 'LayoutProps'` on a fresh
checkout, because Next.js generates that type.

## Backend version and CORS

This app needs a backend that includes
[ucs31-kimathi-backend#20](https://github.com/RAM-AS-RAP/ucs31-kimathi-backend/pull/20)
(volunteer name on login; patient code, age group and sex on results) and
[#21](https://github.com/RAM-AS-RAP/ucs31-kimathi-backend/pull/21) (Kenyan phone numbers,
timestamps in UTC with a `Z`). Merge order: backend #20, backend #21, then this frontend.
On an older backend the app still runs, but results show "Sex not recorded" and similar,
and times are three hours early in Kenya.

The browser only lets the app call the backend if the backend lists the app's address.
Set `CORS_ORIGINS` in the backend's `.env` to the exact origin the app is opened from,
comma-separated if more than one: `http://localhost:3000` (the default) in development,
and the deployed frontend URL in production. A different port counts as a different origin.

## Screens

| Path | Who | What |
|---|---|---|
| `/login` | everyone | Phone number and password |
| `/` | logged in | Volunteer name, start an assessment, recent assessments |
| `/assess` | logged in | Patient code, age and sex, then 35 questions in 7 pages of 5, danger signs first. Next unlocks when all 5 are answered. Danger signs take Yes or No only; once they are answered with a Yes, "Get urgent result now" sends the result straight away |
| `/result/[id]` | logged in | The result straight after sending |
| `/history/[id]` | logged in | A past result, read-only, exactly as first shown |
| `/admin` | admins | Add a volunteer account |

Every result follows the same order: what was found, what to do (the largest block, coloured
by referral level), supporting detail, then the disclaimer. Red is used only for urgent referral.

Phones get the design as drawn. From 768px wide (tablets, laptops) each page centres its content,
and from 1024px home and results switch to two columns, so a supervisor at a computer or a
projected demo sees a full-size layout.

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
