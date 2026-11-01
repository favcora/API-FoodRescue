"""Formato padronizado de erro: {"erro": {"codigo": ..., "mensagem": ..., "detalhes": [...]}}."""
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas import ErroOut


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        codigo: str,
        mensagem: str,
        detalhes: Optional[list[dict]] = None,
        headers: Optional[dict] = None,
    ) -> None:
        self.status_code = status_code
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes or []
        self.headers = headers


def _corpo(codigo: str, mensagem: str, detalhes: Optional[list[dict]] = None) -> dict:
    return {"erro": {"codigo": codigo, "mensagem": mensagem, "detalhes": detalhes or []}}


# Respostas de erro 
ERROS_COMUNS = {
    400: {"model": ErroOut, "description": "Dados de entrada inválidos"},
    401: {"model": ErroOut, "description": "Token ausente, inválido ou expirado"},
    403: {"model": ErroOut, "description": "Papel sem permissão para esta ação"},
    404: {"model": ErroOut, "description": "Recurso não encontrado"},
    409: {"model": ErroOut, "description": "Conflito com o estado atual do recurso"},
}

_CODIGOS_HTTP = {
    401: "NAO_AUTENTICADO",
    403: "ACESSO_NEGADO",
    404: "NAO_ENCONTRADO",
    405: "METODO_NAO_PERMITIDO",
}


def instalar_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_corpo(exc.codigo, exc.mensagem, exc.detalhes),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validacao(_request: Request, exc: RequestValidationError):
        detalhes = []
        for erro in exc.errors():
            caminho = [str(p) for p in erro["loc"] if p not in ("body", "query", "path")]
            mensagem = str(erro["msg"]).removeprefix("Value error, ")
            detalhes.append({"campo": ".".join(caminho) or None, "mensagem": mensagem})
        return JSONResponse(
            status_code=400,
            content=_corpo("VALIDACAO", "Os dados enviados são inválidos.", detalhes),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException):
        codigo = _CODIGOS_HTTP.get(exc.status_code, "ERRO_HTTP")
        mensagem = "Recurso não encontrado." if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_corpo(codigo, mensagem),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _inesperado(_request: Request, _exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_corpo("ERRO_INTERNO", "Erro interno do servidor."),
        )
