from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import acesso_negado, exigir_papeis, get_current_user, get_db, obter_ou_404
from app.errors import ERROS_COMUNS, AppError
from app.models import Doador, Lote, Usuario
from app.pagination import aplicar_ordenacao, paginar, parametros_paginacao
from app.schemas import DoadorOut, DoadorUpdate, Pagina

router = APIRouter(prefix="/api/v1/doadores", tags=["Doadores"], responses=ERROS_COMUNS)


def _pode_acessar(usuario: Usuario, doador: Doador) -> bool:
    return usuario.papel == "admin" or (usuario.doador is not None and usuario.doador.id == doador.id)


@router.get("", response_model=Pagina[DoadorOut], summary="Listar doadores (admin)")
def listar_doadores(
    request: Request,
    nome: Optional[str] = Query(None, description="Filtra por parte do nome."),
    ordenar: Optional[str] = Query(None, description="nome, criado_em (use '-' para decrescente)."),
    paginacao: tuple[int, int] = Depends(parametros_paginacao),
    _admin: Usuario = Depends(exigir_papeis("admin")),
    db: Session = Depends(get_db),
):
    stmt = select(Doador)
    if nome:
        stmt = stmt.where(Doador.nome.ilike(f"%{nome}%"))
    stmt = aplicar_ordenacao(stmt, Doador, ordenar, {"nome", "criado_em"}, "nome")
    return paginar(db, stmt, request, *paginacao, lambda d: DoadorOut.model_validate(d))


@router.get("/{doador_id}", response_model=DoadorOut, summary="Detalhar doador")
def obter_doador(
    doador_id: int, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
):
    doador = obter_ou_404(db, Doador, doador_id, "Doador")
    if not _pode_acessar(usuario, doador):
        raise acesso_negado()
    return doador


@router.patch("/{doador_id}", response_model=DoadorOut, summary="Atualizar doador")
def atualizar_doador(
    doador_id: int,
    body: DoadorUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doador = obter_ou_404(db, Doador, doador_id, "Doador")
    if not _pode_acessar(usuario, doador):
        raise acesso_negado()
    for campo, valor in body.model_dump(exclude_unset=True).items():
        if valor is not None or campo == "endereco":
            setattr(doador, campo, valor)
    db.commit()
    return doador


@router.delete("/{doador_id}", status_code=204, summary="Remover doador (admin)")
def remover_doador(
    doador_id: int,
    _admin: Usuario = Depends(exigir_papeis("admin")),
    db: Session = Depends(get_db),
):
    doador = obter_ou_404(db, Doador, doador_id, "Doador")
    if db.scalar(select(Lote.id).where(Lote.doador_id == doador.id, Lote.status == "reservado")):
        raise AppError(409, "CONFLITO", "O doador possui lotes reservados para resgate.")
    db.delete(doador.usuario)  # remove o usuário e, em cascata, o doador, os lotes e os resgates
    db.commit()
    return Response(status_code=204)
