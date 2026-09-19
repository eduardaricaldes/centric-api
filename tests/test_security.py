from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import Settings, settings
from app.core.security import create_access_token


def test_validade_padrao_do_token_e_de_oito_horas():
    default_settings = Settings(
        database_url="postgresql://user:password@localhost/test",
        secret_key="test-secret",
        _env_file=None,
    )

    assert default_settings.access_token_expire_minutes == 480


def test_access_token_expira_em_oito_horas():
    issued_not_before = datetime.now(timezone.utc)
    token = create_access_token({"sub": "user@example.com"})
    issued_not_after = datetime.now(timezone.utc)

    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )
    expires_at = datetime.fromtimestamp(payload["exp"], timezone.utc)

    assert expires_at - issued_not_after >= timedelta(minutes=479, seconds=59)
    assert expires_at - issued_not_before <= timedelta(minutes=480, seconds=1)
