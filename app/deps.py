from typing import Optional, Type

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.errors import AppError
from app.models import Usuario
from app.security import decode_access_token

bearer = HTTPBearer(
    auto_error=False,
    description="Cole o token obtido em POST /api/v1/tokens.",
)


def get_db():
    with SessionLocal() as db:
        yield db


def get_current_user(
    credenciais: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    cabecalho = {"WWW-Authenticate": "Bearer"}
    if credenciais is None:
        raise AppError(401, "NAO_AUTENTICADO", "Envie o token no cabeçalho Authorization: Bearer <token>.", headers=cabecalho)
    try:
        payload = decode_access_token(credenciais.credentials)
        usuario_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AppError(401, "TOKEN_INVALIDO", "Token inválido ou expirado.", headers=cabecalho)
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise AppError(401, "TOKEN_INVALIDO", "Usuário do token não existe mais.", headers=cabecalho)
    return usuario


def exigir_papeis(*papeis: str):
    def verificador(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.papel not in papeis:
            raise AppError(
                403,
                "ACESSO_NEGADO",
                f"Esta ação é permitida apenas para: {', '.join(papeis)}.",
            )
        return usuario

    return verificador


def obter_ou_404(db: Session, modelo: Type, id_: int, nome: str):
    objeto = db.get(modelo, id_)
    if objeto is None:
        raise AppError(404, "NAO_ENCONTRADO", f"{nome} {id_} não encontrado(a).")
    return objeto


def acesso_negado(mensagem: str = "Você não tem permissão para acessar este recurso.") -> AppError:
    return AppError(403, "ACESSO_NEGADO", mensagem)
