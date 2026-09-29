"""Creates SSO provider rows from a JSON file on api_server startup, so a
deployment (for example the local Keycloak stack) can ship with SSO
preconfigured. Rows are matched by name and never modified once they exist,
so admin edits in the UI win."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy.orm import Session

from onyx.auth.saml_metadata import InvalidSAMLMetadata, fetch_saml_idp_metadata
from onyx.auth.sso_url_guard import UnsafeSSOUrl
from onyx.configs.app_configs import SSO_PROVIDERS_BOOTSTRAP_FILE
from onyx.db.enums import SSOProviderType
from onyx.db.sso_provider import (
    create_sso_provider,
    fetch_sso_provider_by_name,
    set_sso_provider_enabled,
)
from onyx.server.manage.get_state import invalidate_sso_provider_options_cache
from onyx.utils.logger import setup_logger
from shared_configs.configs import MULTI_TENANT

logger = setup_logger()

METADATA_URL_KEY = "idp_metadata_url"


class BootstrapSSOProvider(BaseModel):
    name: str
    display_name: str
    provider_type: SSOProviderType
    config: dict[str, Any]
    allowed_email_domains: list[str] = []
    enabled: bool = True

    @field_validator("provider_type", mode="before")
    @classmethod
    def _case_insensitive_type(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value


def _expand_env(value: Any) -> Any:
    """Expands ${VAR} in string values so secrets can stay in the env file."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def load_bootstrap_providers(path: Path) -> list[BootstrapSSOProvider]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("SSO bootstrap file must contain a JSON list")
    return [BootstrapSSOProvider.model_validate(_expand_env(item)) for item in raw]


def resolve_provider_config(provider: BootstrapSSOProvider) -> dict[str, Any]:
    """Replaces a SAML idp_metadata_url with the IdP fields read from it."""
    config = dict(provider.config)
    metadata_url = config.pop(METADATA_URL_KEY, None)
    if provider.provider_type is SSOProviderType.SAML and metadata_url:
        metadata = fetch_saml_idp_metadata(metadata_url)
        config = {**metadata.model_dump(), **config}
    return config


def bootstrap_sso_providers(db_session: Session) -> None:
    if not SSO_PROVIDERS_BOOTSTRAP_FILE or MULTI_TENANT:
        return
    path = Path(SSO_PROVIDERS_BOOTSTRAP_FILE)
    try:
        providers = load_bootstrap_providers(path)
    except (OSError, ValueError, ValidationError) as e:
        logger.error("Skipping SSO bootstrap: cannot read %s: %s", path, e)
        return

    created = False
    for provider in providers:
        if fetch_sso_provider_by_name(db_session, provider.name) is not None:
            logger.debug("SSO provider %s already exists, skipping", provider.name)
            continue
        try:
            row = create_sso_provider(
                db_session=db_session,
                name=provider.name,
                display_name=provider.display_name,
                provider_type=provider.provider_type,
                config=resolve_provider_config(provider),
                allowed_email_domains=provider.allowed_email_domains,
            )
            if not provider.enabled:
                set_sso_provider_enabled(db_session, row.id, enabled=False)
        except (InvalidSAMLMetadata, UnsafeSSOUrl, ValueError) as e:
            # The next api_server start retries, e.g. once the IdP is up.
            db_session.rollback()
            logger.error("Could not bootstrap SSO provider %s: %s", provider.name, e)
            continue
        created = True
        logger.notice("Bootstrapped SSO provider %s", provider.name)

    if created:
        invalidate_sso_provider_options_cache()
