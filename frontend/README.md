# Secure RAG frontend

React + TypeScript + Vite + Tailwind UI for the secure, multi-tenant RAG API.

## Structure

```text
src/
  components/       reusable layout and UI primitives
  data/              navigation and static UI configuration
  features/         feature-owned pages and interactions
  lib/               typed API client and session transport
  types.ts           cross-feature UI contracts
```

Feature pages are intentionally kept separate from the app shell. The API client keeps access tokens in memory and uses the backend’s HttpOnly refresh cookie; it does not persist bearer tokens in local or session storage.

## Development

```bash
cp .env.example .env
npm install
npm run dev
```

Use `npm ci` in CI and for reproducible local installs when `package-lock.json`
is already present.

Set `VITE_API_BASE_URL=http://localhost:8000` to connect to the FastAPI service. The application starts on the sign-in page when no refresh session is available; the workspace is never rendered as an unauthenticated demo. Invitations are opened with `/?invite=<one-time-token>`.

## Security UX

- Organization switching updates the server-issued tenant context.
- Conversational responses are labeled and explicitly state that no workspace facts were used.
- Grounded answers display source citations; refused answers display the authorization boundary.
- Admin monitoring and organization access-management screens are role-gated in the UI and enforced again by the API.
- Theme preference is local to the browser and can be changed from the top bar or settings.
