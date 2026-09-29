# Local Keycloak for SSO testing (OIDC + SAML)

`docker-compose.local-fork.yml` starts Keycloak with the realm in
`realm-onyx.json` and tells the api_server to create two SSO providers from
`sso-providers.json` on startup (`SSO_PROVIDERS_BOOTSTRAP_FILE`).

| Item | Value |
| --- | --- |
| Keycloak console | http://keycloak.localhost:8180 (admin / admin) |
| Realm | `onyx` |
| OIDC client | `onyx`, confidential, secret from `KEYCLOAK_OIDC_CLIENT_SECRET` |
| SAML client | `onyx-saml` (entity ID), ACS `http://localhost:3030/auth/saml/callback` |
| Test users | `admin@example.com`, `jan.kowalski@example.com`, `maria.nowak@example.com` (password `Password123!`) |

## Host name

OIDC requires the discovery URL to match the issuer. The browser and the
api_server both reach Keycloak as `http://keycloak.localhost:8180`:

- Chrome and Firefox resolve `*.localhost` to `127.0.0.1`.
- Inside Docker, `keycloak.localhost` is a network alias of the Keycloak container.

If your browser does not resolve it (for example Safari), add this line to
`/etc/hosts`:

```
127.0.0.1 keycloak.localhost
```

## Use a real Keycloak

1. In Keycloak, create an OIDC client (confidential, standard flow) with the
   redirect URI `https://<onyx>/api/auth/oidc/<provider-name>/callback`, and/or
   a SAML client whose client ID is the SP entity ID and whose ACS URL is
   `https://<onyx>/auth/saml/callback`. Map the user email to a SAML attribute
   named `email`.
2. In Onyx, open Admin Panel > SSO Providers > Add Provider:
   - OIDC: discovery URL `https://<keycloak>/realms/<realm>/.well-known/openid-configuration`.
   - SAML: paste `https://<keycloak>/realms/<realm>/protocol/saml/descriptor`
     into "Import from IdP metadata" to fill the IdP fields.
3. Or ship the providers as JSON with `SSO_PROVIDERS_BOOTSTRAP_FILE` (see
   `sso-providers.json`; `${VAR}` values are read from the environment, and a
   SAML entry may give `idp_metadata_url` instead of the IdP fields).

`ALLOW_INSECURE_SSO_IDP_URLS=true` lets the IdP use plain http and a private
address. Use it only for local development.
