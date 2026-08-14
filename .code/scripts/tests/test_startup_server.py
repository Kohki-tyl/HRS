import pytest

from scripts.startup import server


def test_port_uses_platform_value(monkeypatch):
    monkeypatch.setenv("PORT", "9000")
    assert server._port() == 9000


@pytest.mark.parametrize("value", ["abc", "0", "65536"])
def test_port_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("PORT", value)
    with pytest.raises(RuntimeError):
        server._port()


def test_production_requires_non_default_admin_password(monkeypatch):
    monkeypatch.setenv("HRS_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", "hrs-admin")
    with pytest.raises(RuntimeError):
        server._validate_production_environment()


def test_production_accepts_configured_admin_password(monkeypatch):
    monkeypatch.setenv("HRS_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-long-production-password")
    server._validate_production_environment()
