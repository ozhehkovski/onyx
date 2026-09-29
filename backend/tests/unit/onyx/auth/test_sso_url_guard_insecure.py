from unittest.mock import patch

import pytest

from onyx.auth import sso_url_guard
from onyx.auth.sso_url_guard import UnsafeSSOUrl, validate_idp_url


def test_insecure_flag_allows_http_private_idp() -> None:
    with (
        patch.object(sso_url_guard, "ALLOW_INSECURE_SSO_IDP_URLS", True),
        patch.object(sso_url_guard, "get_security_settings") as settings,
    ):
        validate_idp_url(
            "http://127.0.0.1:8180/realms/onyx/.well-known/openid-configuration",
            field="openid_config_url",
        )
    settings.assert_not_called()


def test_insecure_flag_keeps_metadata_floor_and_credentials_check() -> None:
    with patch.object(sso_url_guard, "ALLOW_INSECURE_SSO_IDP_URLS", True):
        with pytest.raises(UnsafeSSOUrl):
            validate_idp_url("http://169.254.169.254/latest", field="openid_config_url")
        with pytest.raises(UnsafeSSOUrl):
            validate_idp_url("http://u:p@127.0.0.1/x", field="openid_config_url")
