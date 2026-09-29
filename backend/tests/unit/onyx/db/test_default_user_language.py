import pytest

from onyx.db.enums import default_user_language


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "en"), ("", "en"), ("pl", "pl"), (" PL ", "pl"), ("xx", "en")],
)
def test_default_user_language(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: str
) -> None:
    if value is None:
        monkeypatch.delenv("DEFAULT_USER_LANGUAGE", raising=False)
    else:
        monkeypatch.setenv("DEFAULT_USER_LANGUAGE", value)
    assert default_user_language() == expected
