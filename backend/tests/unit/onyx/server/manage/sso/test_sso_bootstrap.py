import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from onyx.auth.saml_metadata import (
    InvalidSAMLMetadata,
    SAMLIdPMetadata,
    parse_saml_idp_metadata,
)
from onyx.db.enums import SSOProviderType
from onyx.server.manage.sso import bootstrap
from onyx.server.manage.sso.bootstrap import (
    BootstrapSSOProvider,
    load_bootstrap_providers,
    resolve_provider_config,
)

# Shape of Keycloak's /realms/<realm>/protocol/saml/descriptor.
KEYCLOAK_DESCRIPTOR = """<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    entityID="http://localhost:8180/realms/onyx">
  <md:IDPSSODescriptor WantAuthnRequestsSigned="false"
      protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:KeyDescriptor use="signing">
      <ds:KeyInfo><ds:X509Data>
        <ds:X509Certificate>MIICnTCCAYUCBgGTESTCERT</ds:X509Certificate>
      </ds:X509Data></ds:KeyInfo>
    </md:KeyDescriptor>
    <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
    <md:SingleSignOnService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        Location="http://localhost:8180/realms/onyx/protocol/saml"/>
    <md:SingleSignOnService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        Location="http://localhost:8180/realms/onyx/protocol/saml"/>
  </md:IDPSSODescriptor>
</md:EntityDescriptor>
"""


def test_parse_keycloak_descriptor() -> None:
    metadata = parse_saml_idp_metadata(KEYCLOAK_DESCRIPTOR)
    assert metadata == SAMLIdPMetadata(
        idp_entity_id="http://localhost:8180/realms/onyx",
        idp_sso_url="http://localhost:8180/realms/onyx/protocol/saml",
        idp_x509_cert="MIICnTCCAYUCBgGTESTCERT",
    )


def test_parse_rejects_non_metadata() -> None:
    with pytest.raises(InvalidSAMLMetadata):
        parse_saml_idp_metadata("<html>not metadata</html>")
    with pytest.raises(InvalidSAMLMetadata):
        parse_saml_idp_metadata("not even xml")


def test_load_bootstrap_providers_expands_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KC_URL", "http://keycloak:8080")
    monkeypatch.setenv("KC_SECRET", "s3cret")
    path = tmp_path / "sso.json"
    path.write_text(
        json.dumps(
            [
                {
                    "name": "keycloak",
                    "display_name": "Keycloak",
                    "provider_type": "oidc",
                    "config": {
                        "client_id": "onyx",
                        "client_secret": "${KC_SECRET}",
                        "openid_config_url": "${KC_URL}/realms/onyx/.well-known/openid-configuration",
                    },
                }
            ]
        )
    )
    [provider] = load_bootstrap_providers(path)
    assert provider.provider_type is SSOProviderType.OIDC
    assert provider.enabled is True
    assert provider.config["client_secret"] == "s3cret"
    assert provider.config["openid_config_url"].startswith("http://keycloak:8080/")


def test_load_bootstrap_providers_requires_list(tmp_path: Path) -> None:
    path = tmp_path / "sso.json"
    path.write_text("{}")
    with pytest.raises(ValueError):
        load_bootstrap_providers(path)


def test_resolve_saml_config_reads_metadata_url() -> None:
    provider = BootstrapSSOProvider(
        name="keycloak-saml",
        display_name="Keycloak (SAML)",
        provider_type=SSOProviderType.SAML,
        config={"sp_entity_id": "onyx-saml", "idp_metadata_url": "http://kc/desc"},
    )
    metadata = SAMLIdPMetadata(
        idp_entity_id="e", idp_sso_url="http://kc/sso", idp_x509_cert="CERT"
    )
    with patch.object(
        bootstrap, "fetch_saml_idp_metadata", return_value=metadata
    ) as fetch:
        config = resolve_provider_config(provider)
    fetch.assert_called_once_with("http://kc/desc")
    assert config == {
        "idp_entity_id": "e",
        "idp_sso_url": "http://kc/sso",
        "idp_x509_cert": "CERT",
        "sp_entity_id": "onyx-saml",
    }


def _write_providers(tmp_path: Path, providers: list[dict[str, Any]]) -> str:
    path = tmp_path / "sso.json"
    path.write_text(json.dumps(providers))
    return str(path)


def test_bootstrap_creates_only_missing_providers(tmp_path: Path) -> None:
    path = _write_providers(
        tmp_path,
        [
            {
                "name": "existing",
                "display_name": "Existing",
                "provider_type": "oidc",
                "config": {},
            },
            {
                "name": "new-one",
                "display_name": "New",
                "provider_type": "oidc",
                "config": {"client_id": "a", "client_secret": "b"},
                "enabled": False,
            },
        ],
    )
    db_session = MagicMock()
    created_row = MagicMock(id=7)
    with (
        patch.object(bootstrap, "SSO_PROVIDERS_BOOTSTRAP_FILE", path),
        patch.object(bootstrap, "MULTI_TENANT", False),
        patch.object(
            bootstrap,
            "fetch_sso_provider_by_name",
            side_effect=lambda _db, name: MagicMock() if name == "existing" else None,
        ),
        patch.object(
            bootstrap, "create_sso_provider", return_value=created_row
        ) as create,
        patch.object(bootstrap, "set_sso_provider_enabled") as set_enabled,
        patch.object(bootstrap, "invalidate_sso_provider_options_cache") as invalidate,
    ):
        bootstrap.bootstrap_sso_providers(db_session)

    create.assert_called_once()
    assert create.call_args.kwargs["name"] == "new-one"
    set_enabled.assert_called_once_with(db_session, 7, enabled=False)
    invalidate.assert_called_once()


def test_bootstrap_skips_failed_provider_and_continues(tmp_path: Path) -> None:
    path = _write_providers(
        tmp_path,
        [
            {
                "name": "bad",
                "display_name": "Bad",
                "provider_type": "oidc",
                "config": {},
            },
            {
                "name": "good",
                "display_name": "Good",
                "provider_type": "oidc",
                "config": {},
            },
        ],
    )
    db_session = MagicMock()

    def create(**kwargs: Any) -> MagicMock:
        if kwargs["name"] == "bad":
            raise ValueError("invalid oidc provider config")
        return MagicMock(id=1)

    with (
        patch.object(bootstrap, "SSO_PROVIDERS_BOOTSTRAP_FILE", path),
        patch.object(bootstrap, "MULTI_TENANT", False),
        patch.object(bootstrap, "fetch_sso_provider_by_name", return_value=None),
        patch.object(
            bootstrap, "create_sso_provider", side_effect=create
        ) as create_mock,
        patch.object(bootstrap, "invalidate_sso_provider_options_cache"),
    ):
        bootstrap.bootstrap_sso_providers(db_session)

    assert create_mock.call_count == 2
    db_session.rollback.assert_called_once()


def test_bootstrap_noop_without_file() -> None:
    db_session = MagicMock()
    with (
        patch.object(bootstrap, "SSO_PROVIDERS_BOOTSTRAP_FILE", None),
        patch.object(bootstrap, "create_sso_provider") as create,
    ):
        bootstrap.bootstrap_sso_providers(db_session)
    create.assert_not_called()
