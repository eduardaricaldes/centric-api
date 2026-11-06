import pytest
from starlette.requests import Request

from app.core.config import Settings, settings
from app.core.rate_limit import client_ip, limiter


@pytest.fixture()
def rate_limit_on():
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def test_login_bloqueia_apos_10_tentativas_por_minuto(client, rate_limit_on):
    for _ in range(10):
        response = client.post(
            "/auth/login",
            data={"username": "naoexiste@north.com", "password": "errada"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login",
        data={"username": "naoexiste@north.com", "password": "errada"},
    )
    assert blocked.status_code == 429


def test_register_bloqueia_apos_5_tentativas_por_minuto(client, rate_limit_on):
    for _ in range(5):
        response = client.post(
            "/auth/register",
            json={"name": "X", "email": "x@north.com", "password": "12345678"},
        )
        assert response.status_code == 403  # sem invite_token, mas conta na cota

    blocked = client.post(
        "/auth/register",
        json={"name": "X", "email": "x@north.com", "password": "12345678"},
    )
    assert blocked.status_code == 429


def test_reset_password_bloqueia_apos_5_tentativas_por_minuto(client, rate_limit_on):
    for _ in range(5):
        response = client.post(
            "/auth/reset-password",
            json={"token": "invalido", "new_password": "12345678"},
        )
        assert response.status_code == 403

    blocked = client.post(
        "/auth/reset-password",
        json={"token": "invalido", "new_password": "12345678"},
    )
    assert blocked.status_code == 429


def request_from(client_host: str, forwarded: str | None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": (client_host, 1)})


def test_ignora_x_forwarded_for_quando_nao_confia_no_proxy(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", False)

    assert client_ip(request_from("10.0.0.1", "1.2.3.4")) == "10.0.0.1"


def test_usa_x_forwarded_for_atras_de_proxy_confiavel(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", True)

    assert client_ip(request_from("10.0.0.1", "1.2.3.4, 10.0.0.1")) == "1.2.3.4"
    assert client_ip(request_from("10.0.0.1", None)) == "10.0.0.1"


def test_url_postgres_vira_postgresql():
    config = Settings(database_url="postgres://u:p@host/db", secret_key="x")

    assert config.database_url == "postgresql://u:p@host/db"
