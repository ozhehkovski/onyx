# Onyx fork: Polish UI, Keycloak SSO, chat insights

This fork adds the features below to the MIT-licensed Community Edition. It does
not use or change code in `ee/` directories, and the local stack runs with
`LICENSE_ENFORCEMENT_ENABLED=false`, so no Enterprise code is loaded.

## Features

| Feature | Where |
| --- | --- |
| Polish UI (`pl`), 5,600+ strings | `web/src/i18n/messages/pl.json`; pick it in Settings > Language |
| Default language for new users and the login page | `DEFAULT_USER_LANGUAGE` (api_server), `DEFAULT_LOCALE` (web_server) |
| Keycloak SSO over OIDC and SAML | Admin Panel > SSO Providers; `deployment/docker_compose/keycloak/` |
| SSO providers from a file at startup | `SSO_PROVIDERS_BOOTSTRAP_FILE` |
| SAML metadata import (URL, e.g. Keycloak descriptor) | SSO provider form; `POST /api/admin/sso/saml-metadata` |
| Chat usage dashboard | Admin Panel > Usage > Chat Usage (`/admin/chat-insights/usage`) |
| Chat ratings analytics | Admin Panel > Usage > Chat Ratings (`/admin/chat-insights/feedback`) |
| Query history with filters and chat view | Admin Panel > Usage > Chat History (`/admin/chat-insights/history`) |
| Chat export (JSON / CSV) for admins | Chat History page, `GET /api/admin/chat-insights/export` |
| "Export my chats" for every user | Settings > General, `GET /api/user/chat-export` |

`ONYX_QUERY_HISTORY_TYPE` controls privacy: `normal` shows emails,
`anonymized` shows stable pseudonyms (`user-1a2b3c4d`), `disabled` turns off
history and export.

## Fixes found while testing with Keycloak

- SAML: accept repeated attribute names (Keycloak sends one `Role` attribute per role).
- SAML: after the IdP form POST, redirect the browser into the app. Before,
  nginx sent the POST straight to the API, which answered `204` and left the
  user on the Keycloak page.
- Opal `Table`: `pageSize={Infinity}` rendered no rows (`0 * Infinity = NaN`).

## Run locally

```bash
cd deployment/docker_compose
./start-local-fork.sh
```

Then:

1. Open http://localhost:3030 and sign up with email and password. The first
   account becomes the admin.
2. Optional demo data (Polish chats with ratings):
   `docker exec onyx-fork-api_server-1 python -m onyx.db.seeding.chat_insights_demo`
   (remove it with `--purge`).
3. Sign out and try "Keycloak (OIDC)" and "Keycloak (SAML)" with the test users
   in `deployment/docker_compose/keycloak/README.md`.
4. To chat, add an LLM provider in Admin Panel > Language Models.

The stack uses the Onyx Lite profile (no vector DB, no model servers), so
connectors and document search are off. Stop it with `./start-local-fork.sh down`.
