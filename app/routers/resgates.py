from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.deps import acesso_negado, exigir_papeis, get_current_user, get_db, obter_ou_404
from app.errors import ERROS_COMUNS, AppError
from app.models import Lote, Resgate, Usuario
from app.pagination import aplicar_ordenacao, paginar, parametros_paginacao
from app.schemas import Pagina, ResgateCreate, ResgateOut, ResgateUpdate, StatusResgate
from app.services.compatibilidade import avaliar
from app.services.notificacao import expirar_lotes_vencidos, notificar_proxima_instituicao

router = APIRouter(prefix="/api/v1/resgates", tags=["Resgates"], responses=ERROS_COMUNS)

# Máquina de estados do resgate
TRANSICOES = {
    "notificado": {"aceito", "recusado"},
    "aceito": {"concluido", "cancelado"},
}


def _checar_acesso(usuario: Usuario, resgate: Resgate) -> None:
    if usuario.papel == "admin":
        return
    if usuario.papel == "ong" and usuario.instituicao and resgate.instituicao_id == usuario.instituicao.id:
        return
    if usuario.papel == "doador" and usuario.doador and resgate.lote.doador_id == usuario.doador.id:
        return
    raise acesso_negado()


@router.get("", response_model=Pagina[ResgateOut], summary="Listar resgates")
def listar_resgates(
    request: Request,
    status: Optional[StatusResgate] = Query(None),
    lote_id: Optional[int] = Query(None),
    instituicao_id: Optional[int] = Query(None),
    ordenar: Optional[str] = Query(
        None, description="criado_em, atualizado_em, nota (use '-' para decrescente)."
    ),
    paginacao: tuple[int, int] = Depends(parametros_paginacao),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expirar_lotes_vencidos(db)
    stmt = select(Resgate)
    if usuario.papel == "ong":
        stmt = stmt.where(Resgate.instituicao_id == (usuario.instituicao.id if usuario.instituicao else -1))
    elif usuario.papel == "doador":
        stmt = stmt.join(Lote, Lote.id == Resgate.lote_id).where(
            Lote.doador_id == (usuario.doador.id if usuario.doador else -1)
        )
    if status:
        stmt = stmt.where(Resgate.status == status)
    if lote_id:
        stmt = stmt.where(Resgate.lote_id == lote_id)
    if instituicao_id:
        stmt = stmt.where(Resgate.instituicao_id == instituicao_id)
    stmt = aplicar_ordenacao(stmt, Resgate, ordenar, {"criado_em", "atualizado_em", "nota"}, "-criado_em")
    return paginar(db, stmt, request, *paginacao, lambda r: ResgateOut.model_validate(r))


@router.post(
    "",
    response_model=ResgateOut,
    status_code=201,
    summary="Solicitar resgate de um lote (ONG)",
    description="A ONG pede um lote por conta própria, sem esperar o alerta. O resgate já nasce `aceito`, "
    "o lote fica `reservado` e os alertas abertos de outras ONGs expiram.",
)
def solicitar_resgate(
    body: ResgateCreate,
    response: Response,
    usuario: Usuario = Depends(exigir_papeis("ong")),
    db: Session = Depends(get_db),
):
    expirar_lotes_vencidos(db)
    lote = obter_ou_404(db, Lote, body.lote_id, "Lote")
    if lote.status != "disponivel":
        raise AppError(409, "CONFLITO", f"O lote não está disponível (status atual: {lote.status}).")
    if db.scalar(
        select(Resgate.id).where(
            Resgate.lote_id == lote.id, Resgate.instituicao_id == usuario.instituicao.id
        )
    ):
        raise AppError(409, "CONFLITO", "Sua instituição já tem um resgate para este lote; use PATCH no resgate existente.")

    db.execute(
        update(Resgate)
        .where(Resgate.lote_id == lote.id, Resgate.status == "notificado")
        .values(status="expirado")
    )
    resgate = Resgate(
        lote_id=lote.id,
        instituicao_id=usuario.instituicao.id,
        status="aceito",
        nota=avaliar(lote, usuario.instituicao)["nota"],
        webhook_status="sem_webhook",
    )
    lote.status = "reservado"
    db.add(resgate)
    db.commit()
    db.refresh(resgate)
    response.headers["Location"] = f"/api/v1/resgates/{resgate.id}"
    return resgate


@router.get("/{resgate_id}", response_model=ResgateOut, summary="Detalhar resgate")
def obter_resgate(
    resgate_id: int, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
):
    expirar_lotes_vencidos(db)
    resgate = obter_ou_404(db, Resgate, resgate_id, "Resgate")
    _checar_acesso(usuario, resgate)
    return resgate


@router.patch(
    "/{resgate_id}",
    response_model=ResgateOut,
    summary="Aceitar, recusar, concluir ou cancelar um resgate",
    description="Fluxo: `notificado → aceito | recusado` e `aceito → concluido | cancelado`. "
    "Se a ONG **recusar** (ou cancelar), a API notifica automaticamente a próxima instituição mais compatível.",
)
def atualizar_resgate(
    resgate_id: int,
    body: ResgateUpdate,
    usuario: Usuario = Depends(exigir_papeis("ong", "admin")),
    db: Session = Depends(get_db),
):
    resgate = obter_ou_404(db, Resgate, resgate_id, "Resgate")
    if usuario.papel == "ong" and (
        usuario.instituicao is None or resgate.instituicao_id != usuario.instituicao.id
    ):
        raise acesso_negado("Somente a instituição do resgate (ou o admin) pode alterá-lo.")

    expirar_lotes_vencidos(db)
    db.refresh(resgate)

    novo = body.status
    if novo not in TRANSICOES.get(resgate.status, set()):
        raise AppError(409, "CONFLITO", f"Transição inválida: {resgate.status} → {novo}.")

    lote = resgate.lote
    if novo == "aceito":
        if lote.status != "disponivel":
            raise AppError(409, "CONFLITO", f"O lote não está mais disponível (status atual: {lote.status}).")
        lote.status = "reservado"
        db.execute(
            update(Resgate)
            .where(Resgate.lote_id == lote.id, Resgate.id != resgate.id, Resgate.status == "notificado")
            .values(status="expirado")
        )
    elif novo == "concluido":
        lote.status = "resgatado"
    elif novo == "cancelado":
        lote.status = "disponivel"

    resgate.status = novo
    db.commit()

    if novo in ("recusado", "cancelado"):
        notificar_proxima_instituicao(db, lote)

    db.refresh(resgate)
    return resgate


@router.delete("/{resgate_id}", status_code=204, summary="Remover resgate encerrado (admin)")
def remover_resgate(
    resgate_id: int,
    _admin: Usuario = Depends(exigir_papeis("admin")),
    db: Session = Depends(get_db),
):
    resgate = obter_ou_404(db, Resgate, resgate_id, "Resgate")
    if resgate.status not in ("recusado", "cancelado", "expirado"):
        raise AppError(409, "CONFLITO", "Só é possível remover resgates recusados, cancelados ou expirados.")
    db.delete(resgate)
    db.commit()
    return Response(status_code=204)
