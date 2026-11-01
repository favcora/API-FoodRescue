import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def hash_password(senha: str) -> str:
    salt = os.urandom(16)
    iteracoes = settings.password_iterations
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, iteracoes)
    return f"pbkdf2_sha256${iteracoes}${salt.hex()}${digest.hex()}"


def verify_password(senha: str, armazenado: str) -> bool:
    try:
        _algoritmo, iteracoes, salt, digest = armazenado.split("$")
        calculado = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), int(iteracoes))
    except ValueError:
        return False
    return hmac.compare_digest(calculado.hex(), digest)


def create_access_token(usuario_id: int, papel: str) -> tuple[str, int]:
    validade = timedelta(minutes=settings.access_token_minutes)
    agora = datetime.now(timezone.utc)
    payload = {"sub": str(usuario_id), "papel": papel, "iat": agora, "exp": agora + validade}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, int(validade.total_seconds())


def decode_access_token(token: str) -> dict:
    """Levanta jwt.PyJWTError se o token for inválido ou estiver expirado."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
