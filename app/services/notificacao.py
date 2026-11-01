"""Cria o resgate e dispara o webhook para a próxima instituição mais compatível."""
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Instituicao, Lote, Resgate
from app.services import webhook
from app.services.compatibilidade import ranquear_instituicoes
from app.utils import utcnow


def expirar_lotes_vencidos(db: Session) -> None:
    """Lotes disponíveis cujo prazo passou viram 'expirado' (e seus alertas abertos também)."""
    ids = list(
        db.scalars(
            select(Lote.id).where(Lote.status == "disponivel", Lote.disponivel_ate < utcnow())
        )
    )
    if not ids:
        return
    db.execute(
        update(Resgate)
        .where(Resgate.lote_id.in_(ids), Resgate.status == "notificado")
        .values(status="expirado")
    )
    db.execute(update(Lote).where(Lote.id.in_(ids)).values(status="expirado"))
    db.commit()


def notificar_proxima_instituicao(db: Session, lote: Lote) -> Optional[Resgate]:
    """Notifica a instituição mais compatível que ainda não foi consultada para este lote."""
    if lote.status != "disponivel" or lote.disponivel_ate <= utcnow():
        return None

    ja_consultadas = list(db.scalars(select(Resgate.instituicao_id).where(Resgate.lote_id == lote.id)))
    ranking = ranquear_instituicoes(db, lote, excluir_ids=ja_consultadas, limite=1)
    if not ranking:
        return None

    melhor = ranking[0]
    resgate = Resgate(
        lote_id=lote.id,
        instituicao_id=melhor["instituicao_id"],
        status="notificado",
        nota=melhor["nota"],
        webhook_status="pendente",
    )
    db.add(resgate)
    db.commit()
    db.refresh(resgate)

    instituicao = db.get(Instituicao, melhor["instituicao_id"])
    payload = webhook.montar_payload(resgate, lote, instituicao, melhor)
    resgate.webhook_status = webhook.send_webhook(instituicao, payload)
    db.commit()
    return resgate
