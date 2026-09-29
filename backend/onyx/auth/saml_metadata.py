"""Reads SAML IdP metadata (e.g. Keycloak's
/realms/<realm>/protocol/saml/descriptor) into the IdP fields of a SAML
provider config."""

import httpx
from onelogin.saml2.constants import OneLogin_Saml2_Constants
from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
from pydantic import BaseModel

from onyx.auth.sso_url_guard import validate_idp_url

_FETCH_TIMEOUT_SECONDS = 10
_MAX_METADATA_BYTES = 1_000_000


class SAMLIdPMetadata(BaseModel):
    idp_entity_id: str
    idp_sso_url: str
    idp_x509_cert: str


class InvalidSAMLMetadata(ValueError):
    """The document is not usable IdP metadata."""


def parse_saml_idp_metadata(metadata_xml: str) -> SAMLIdPMetadata:
    try:
        parsed = OneLogin_Saml2_IdPMetadataParser.parse(
            metadata_xml,
            required_sso_binding=OneLogin_Saml2_Constants.BINDING_HTTP_REDIRECT,
        )
    except Exception as e:
        raise InvalidSAMLMetadata(f"could not parse SAML metadata: {e}") from e

    idp = parsed.get("idp")
    if not isinstance(idp, dict):
        raise InvalidSAMLMetadata("metadata has no IDPSSODescriptor")

    entity_id = idp.get("entityId")
    sso_service = idp.get("singleSignOnService")
    sso_url = sso_service.get("url") if isinstance(sso_service, dict) else None
    cert = idp.get("x509cert")
    if not cert:
        # Several signing keys (e.g. during key rotation): take the first one.
        signing_certs = (idp.get("x509certMulti") or {}).get("signing") or []
        cert = signing_certs[0] if signing_certs else None

    if not entity_id or not sso_url or not cert:
        raise InvalidSAMLMetadata(
            "metadata must contain an entityID, an HTTP-Redirect "
            "SingleSignOnService and a signing certificate"
        )
    return SAMLIdPMetadata(
        idp_entity_id=entity_id, idp_sso_url=sso_url, idp_x509_cert=cert
    )


def fetch_saml_idp_metadata(metadata_url: str) -> SAMLIdPMetadata:
    """Raises UnsafeSSOUrl for a URL the server must not fetch, and
    InvalidSAMLMetadata for any fetch or parse failure."""
    validate_idp_url(metadata_url, field="idp_metadata_url")
    try:
        response = httpx.get(
            metadata_url, timeout=_FETCH_TIMEOUT_SECONDS, follow_redirects=False
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise InvalidSAMLMetadata(f"could not fetch SAML metadata: {e}") from e
    if len(response.content) > _MAX_METADATA_BYTES:
        raise InvalidSAMLMetadata("SAML metadata document is too large")
    return parse_saml_idp_metadata(response.text)
