from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import acesso_negado, exigir_papeis, get_current_user, get_db, obter_ou_404
from app.errors import ERROS_COMUNS, AppError
from app.http_cache import resposta_com_etag
from app.models import Lote, Usuario
from app.pagination import aplicar_ordenacao, paginar, parametros_paginacao
from app.schemas import (
    CategoriaLote,
    CompatibilidadeOut,
    LoteCreate,
    LoteCriadoOut,
    LoteOut,
    LoteUpdate,
    NotificacaoOut,
    Pagina,
    StatusLote,
)
from app.services.compatibilidade import ranquear_instituicoes
from app.services.notificacao import expirar_lotes_vencidos, notificar_proxima_instituicao

router = APIRouter(prefix="/api/v1/lotes-excedentes", tags=["Lotes excedentes"], responses=ERROS_COMUNS)


def _e_dono(usuario: Usuario, lote: Lote) -> bool:
    return usuario.doador is not None and usuario.doador.id == lote.doador_id


def _checar_leitura(usuario: Usuario, lote: Lote) -> None:
    if usuario.papel == "doador" and not _e_dono(usuario, lote):
        raise acesso_negado("Doadores só podem ver os próprios lotes.")


def _checar_escrita(usuario: Usuario, lote: Lote) -> None:
    if usuario.papel == "admin":
        return
    if usuario.papel == "doador" and _e_dono(usuario, lote):
        return
    raise acesso_negado("Somente o doador do lote (ou o admin) pode alterá-lo.")


@router.post(
    "",
    response_model=LoteCriadoOut,
    status_code=201,
    summary="Publicar lote de excedente",
    description="Cria o lote e, automaticamente, calcula a compatibilidade com as instituições "
    "e envia um **webhook** para a mais compatível (cria um resgate com status `notificado`).",
)
def criar_lote(
    body: LoteCreate,
    response: Response,
    usuario: Usuario = Depends(exigir_papeis("doador")),
    db: Session = Depends(get_db),
):
    lote = Lote(**body.model_dump(), doador_id=usuario.doador.id)
    db.add(lote)
    db.commit()
    db.refresh(lote)

    resgate = notificar_proxima_instituicao(db, lote)
    notificacao = None
    if resgate:
        notificacao = NotificacaoOut(
            resgate_id=resgate.id,
            instituicao_id=resgate.instituicao_id,
            nota=resgate.nota,
            webhook_status=resgate.webhook_status,
        )
    response.headers["Location"] = f"/api/v1/lotes-excedentes/{lote.id}"
    return LoteCriadoOut(**LoteOut.model_validate(lote).model_dump(), notificacao=notificacao)


@router.get("", response_model=Pagina[LoteOut], summary="Listar lotes (paginação, filtros e ordenação)")
def listar_lotes(
    request: Request,
    status: Optional[StatusLote] = Query(None),
    categoria: Optional[CategoriaLote] = Query(None),
    doador_id: Optional[int] = Query(None),
    quantidade_min: Optional[float] = Query(None, gt=0, description="kg mínimos."),
    quantidade_max: Optional[float] = Query(None, gt=0, description="kg máximos."),
    ordenar: Optional[str] = Query(
        None, description="criado_em, disponivel_ate, quantidade_kg, status (use '-' para decrescente)."
    ),
    paginacao: tuple[int, int] = Depends(parametros_paginacao),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expirar_lotes_vencidos(db)
    stmt = select(Lote)
    if usuario.papel == "doador":  # doador só enxerga os próprios lotes
        stmt = stmt.where(Lote.doador_id == (usuario.doador.id if usuario.doador else -1))
    if status:
        stmt = stmt.where(Lote.status == status)
    if categoria:
        stmt = stmt.where(Lote.categoria == categoria)
    if doador_id:
        stmt = stmt.where(Lote.doador_id == doador_id)
    if quantidade_min is not None:
        stmt = stmt.where(Lote.quantidade_kg >= quantidade_min)
    if quantidade_max is not None:
        stmt = stmt.where(Lote.quantidade_kg <= quantidade_max)
    stmt = aplicar_ordenacao(
        stmt, Lote, ordenar, {"criado_em", "disponivel_ate", "quantidade_kg", "status"}, "-criado_em"
    )
    return paginar(db, stmt, request, *paginacao, lambda l: LoteOut.model_validate(l))


@router.get(
    "/{lote_id}",
    response_model=LoteOut,
    summary="Detalhar lote (com cache ETag)",
    responses={304: {"description": "Não modificado (o cliente já tem a versão atual)"}},
)
def obter_lote(
    lote_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expirar_lotes_vencidos(db)
    lote = obter_ou_404(db, Lote, lote_id, "Lote")
    _checar_leitura(usuario, lote)
    return resposta_com_etag(request, jsonable_encoder(LoteOut.model_validate(lote)))


@router.patch("/{lote_id}", response_model=LoteOut, summary="Atualizar lote disponível")
def atualizar_lote(
    lote_id: int,
    body: LoteUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expirar_lotes_vencidos(db)
    lote = obter_ou_404(db, Lote, lote_id, "Lote")
    _checar_escrita(usuario, lote)
    if lote.status != "disponivel":
        raise AppError(409, "CONFLITO", f"Só é possível alterar lotes disponíveis (status atual: {lote.status}).")
    for campo, valor in body.model_dump(exclude_unset=True).items():
        if valor is not None:
            setattr(lote, campo, valor)
    db.commit()
    return lote


@router.delete("/{lote_id}", status_code=204, summary="Remover lote")
def remover_lote(
    lote_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lote = obter_ou_404(db, Lote, lote_id, "Lote")
    _checar_escrita(usuario, lote)
    if lote.status == "reservado":
        raise AppError(409, "CONFLITO", "O lote está reservado por uma instituição; cancele o resgate antes.")
    db.delete(lote)
    db.commit()
    return Response(status_code=204)


@router.get(
    "/{lote_id}/compatibilidades",
    response_model=list[CompatibilidadeOut],
    summary="Ranking de instituições mais compatíveis com o lote",
    description="Mostra a nota de compatibilidade (capacidade + distância) de cada instituição ativa "
    "ao alcance, da melhor para a pior. É a mesma regra usada no envio automático do webhook.",
)
def listar_compatibilidades(
    lote_id: int,
    limite: int = Query(5, ge=1, le=20, description="Quantas instituições retornar."),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lote = obter_ou_404(db, Lote, lote_id, "Lote")
    _checar_leitura(usuario, lote)
    return ranquear_instituicoes(db, lote, limite=limite)
