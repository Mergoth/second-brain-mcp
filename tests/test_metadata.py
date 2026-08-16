"""Tests for metadata.py — RFC 9728 protected-resource metadata configuration (ADR-0003)."""

from second_brain_mcp.metadata import build_auth_settings


def test_protected_resource_metadata_lists_authorization_servers() -> None:
    settings = build_auth_settings(
        resource_url="http://127.0.0.1:8000",
        issuer_url="https://auth.example.com",
    )
    assert str(settings.issuer_url) == "https://auth.example.com/"
    assert str(settings.resource_server_url) == "http://127.0.0.1:8000/"


def test_build_auth_settings_defaults() -> None:
    settings = build_auth_settings()
    assert str(settings.resource_server_url) == "http://127.0.0.1:8000/"
    assert str(settings.issuer_url) == "https://auth.example.com/"
