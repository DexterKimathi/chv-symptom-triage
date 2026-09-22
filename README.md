# CHV Symptom Triage: Frontend

**Student:** Dexter Kimathi (166889) · **Group:** U-CS 31

Next.js app for community health volunteers. Build starts week 3 (5-9 October).

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

Opens on http://localhost:3000

## API

All backend calls live in `src/lib/api.ts`. The base URL comes from
`NEXT_PUBLIC_API_BASE_URL` in `.env.local`.

## Notes

Volunteers use low-cost phones on mobile data, so pages stay light: no heavy images, and
only the scripts each page needs.

Every result screen shows a disclaimer and a seek-professional-care message, with referral
guidance as the most prominent element. A result is never presented as a diagnosis.
