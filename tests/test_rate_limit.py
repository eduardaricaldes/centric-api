import pytest

from app.core.rate_limit import limiter


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
