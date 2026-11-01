from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import acesso_negado, exigir_papeis, get_current_user, get_db, obter_ou_404
from app.errors import ERROS_COMUNS, AppError
from app.http_cache import resposta_com_etag
from app.models import Instituicao, Resgate, Usuario
from app.pagination import aplicar_ordenacao, paginar, parametros_paginacao
from app.schemas import InstituicaoOut, InstituicaoUpdate, Pagina

router = APIRouter(prefix="/api/v1/instituicoes", tags=["Instituições"], responses=ERROS_COMUNS)


def _e_dona(usuario: Usuario, instituicao: Instituicao) -> bool:
    return usuario.papel == "admin" or (
        usuario.instituicao is not None and usuario.instituicao.id == instituicao.id
    )


def _serializar(instituicao: Instituicao, usuario: Usuario) -> InstituicaoOut:
    saida = InstituicaoOut.model_validate(instituicao)
    if not _e_dona(usuario, instituicao):
        saida = saida.model_copy(update={"webhook_url": None})  # esconde a URL de quem não é dono
    return saida


@router.get("", response_model=Pagina[InstituicaoOut], summary="Listar instituições")
def listar_instituicoes(
    request: Request,
    ativa: Optional[bool] = Query(None, description="Filtra por instituições ativas/inativas."),
    capacidade_min: Optional[float] = Query(None, gt=0, description="Capacidade mínima (kg)."),
    nome: Optional[str] = Query(None, description="Filtra por parte do nome."),
    ordenar: Optional[str] = Query(None, description="nome, capacidade_kg, criado_em (use '-' para decrescente)."),
    paginacao: tuple[int, int] = Depends(parametros_paginacao),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Instituicao)
    if ativa is not None:
        stmt = stmt.where(Instituicao.ativa.is_(ativa))
    if capacidade_min is not None:
        stmt = stmt.where(Instituicao.capacidade_kg >= capacidade_min)
    if nome:
        stmt = stmt.where(Instituicao.nome.ilike(f"%{nome}%"))
    stmt = aplicar_ordenacao(stmt, Instituicao, ordenar, {"nome", "capacidade_kg", "criado_em"}, "nome")
    return paginar(db, stmt, request, *paginacao, lambda i: _serializar(i, usuario))


@router.get(
    "/{instituicao_id}",
    response_model=InstituicaoOut,
    summary="Detalhar instituição (com cache ETag)",
    responses={304: {"description": "Não modificado (o cliente já tem a versão atual)"}},
)
def obter_instituicao(
    instituicao_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    instituicao = obter_ou_404(db, Instituicao, instituicao_id, "Instituição")
    return resposta_com_etag(request, jsonable_encoder(_serializar(instituicao, usuario)))


@router.patch("/{instituicao_id}", response_model=InstituicaoOut, summary="Atualizar instituição")
def atualizar_instituicao(
    instituicao_id: int,
    body: InstituicaoUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    instituicao = obter_ou_404(db, Instituicao, instituicao_id, "Instituição")
    if not _e_dona(usuario, instituicao):
        raise acesso_negado()
    for campo, valor in body.model_dump(exclude_unset=True).items():
        if campo == "webhook_url":
            instituicao.webhook_url = str(valor) if valor else None
        elif valor is not None:
            setattr(instituicao, campo, valor)
    db.commit()
    return _serializar(instituicao, usuario)


@router.delete("/{instituicao_id}", status_code=204, summary="Remover instituição (admin)")
def remover_instituicao(
    instituicao_id: int,
    _admin: Usuario = Depends(exigir_papeis("admin")),
    db: Session = Depends(get_db),
):
    instituicao = obter_ou_404(db, Instituicao, instituicao_id, "Instituição")
    if db.scalar(
        select(Resgate.id).where(Resgate.instituicao_id == instituicao.id, Resgate.status == "aceito")
    ):
        raise AppError(409, "CONFLITO", "A instituição possui resgates aceitos em andamento.")
    db.delete(instituicao.usuario)
    db.commit()
    return Response(status_code=204)
