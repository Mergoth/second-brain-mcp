"""Tests for metadata.py — RFC 9728 / RFC 8414 settings (ADR-0003, ADR-0004)."""

from second_brain_mcp.metadata import SCOPE, build_auth_settings


def test_urls_are_preserved_verbatim() -> None:
    # RFC 8414 issuer comparison is exact: no trailing slash may be added.
    settings = build_auth_settings(
        resource_url="https://brain.example.net:1986/mcp",
        issuer_url="https://brain.example.net:1986",
    )
    assert str(settings.issuer_url) == "https://brain.example.net:1986"
    assert str(settings.resource_server_url) == "https://brain.example.net:1986/mcp"


def test_static_mode_has_no_registration_or_scopes() -> None:
    settings = build_auth_settings()
    assert str(settings.resource_server_url) == "http://127.0.0.1:8000/mcp"
    assert settings.client_registration_options is None
    assert settings.required_scopes is None


def test_oauth_mode_enables_registration_and_the_vault_scope_but_not_revocation() -> None:
    settings = build_auth_settings(oauth=True)
    assert settings.client_registration_options is not None
    assert settings.client_registration_options.enabled
    assert settings.client_registration_options.default_scopes == [SCOPE]
    # SDK 2.0.0 revocation rejects public clients; see metadata.build_auth_settings.
    assert settings.revocation_options is None
    assert settings.required_scopes == [SCOPE]
