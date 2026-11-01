from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.errors import ERROS_COMUNS, AppError
from app.models import Doador, Instituicao, Usuario
from app.schemas import TokenIn, TokenOut, UsuarioCreate, UsuarioOut
from app.security import create_access_token, hash_password, verify_password

usuarios = APIRouter(prefix="/api/v1/usuarios", tags=["Autenticação"], responses=ERROS_COMUNS)
tokens = APIRouter(prefix="/api/v1/tokens", tags=["Autenticação"], responses=ERROS_COMUNS)


@usuarios.post(
    "",
    response_model=UsuarioOut,
    status_code=201,
    summary="Cadastrar usuário (doador ou ONG)",
    description="Cria o usuário e o perfil (doador ou instituição) de uma vez. "
    "O papel `admin` não pode ser criado por aqui.",
)
def cadastrar_usuario(body: UsuarioCreate, response: Response, db: Session = Depends(get_db)):
    if body.papel == "admin":
        raise AppError(403, "ACESSO_NEGADO", "O papel 'admin' não pode ser criado por cadastro público.")

    email = body.email.lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise AppError(409, "CONFLITO", "Já existe um usuário com este e-mail.")

    usuario = Usuario(email=email, senha_hash=hash_password(body.senha), papel=body.papel)
    if body.papel == "doador":
        usuario.doador = Doador(**body.perfil_doador.model_dump())
    else:
        dados = body.perfil_instituicao.model_dump()
        dados["webhook_url"] = str(dados["webhook_url"]) if dados["webhook_url"] else None
        usuario.instituicao = Instituicao(**dados)

    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "CONFLITO", "Já existe um usuário com este e-mail.")

    if usuario.doador:
        response.headers["Location"] = f"/api/v1/doadores/{usuario.doador.id}"
    else:
        response.headers["Location"] = f"/api/v1/instituicoes/{usuario.instituicao.id}"
    return usuario


@usuarios.get("/me", response_model=UsuarioOut, summary="Dados do usuário logado")
def meu_usuario(usuario: Usuario = Depends(get_current_user)):
    return usuario


@tokens.post(
    "",
    response_model=TokenOut,
    status_code=201,
    summary="Gerar token de acesso (login)",
)
def gerar_token(body: TokenIn, db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.email == body.email.lower()))
    if usuario is None or not verify_password(body.senha, usuario.senha_hash):
        raise AppError(401, "CREDENCIAIS_INVALIDAS", "E-mail ou senha incorretos.")
    token, expira_em = create_access_token(usuario.id, usuario.papel)
    return TokenOut(access_token=token, expires_in=expira_em)
