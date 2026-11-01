from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import exigir_papeis, get_db
from app.errors import ERROS_COMUNS
from app.models import Doador, Instituicao, Lote, Resgate, Usuario
from app.schemas import MetricasImpactoOut
from app.services.notificacao import expirar_lotes_vencidos

router = APIRouter(prefix="/api/v1/metricas", tags=["Métricas"], responses=ERROS_COMUNS)


@router.get("/impacto", response_model=MetricasImpactoOut, summary="Métricas de impacto (admin)")
def metricas_de_impacto(
    _admin: Usuario = Depends(exigir_papeis("admin")), db: Session = Depends(get_db)
):
    expirar_lotes_vencidos(db)

    lotes_por_status = dict(db.execute(select(Lote.status, func.count()).group_by(Lote.status)).all())
    resgates_por_status = dict(
        db.execute(select(Resgate.status, func.count()).group_by(Resgate.status)).all()
    )
    kg_ofertados = db.scalar(select(func.coalesce(func.sum(Lote.quantidade_kg), 0.0))) or 0.0
    kg_resgatados = (
        db.scalar(
            select(func.coalesce(func.sum(Lote.quantidade_kg), 0.0)).where(Lote.status == "resgatado")
        )
        or 0.0
    )

    return MetricasImpactoOut(
        doadores_cadastrados=db.scalar(select(func.count()).select_from(Doador)) or 0,
        instituicoes_ativas=db.scalar(
            select(func.count()).select_from(Instituicao).where(Instituicao.ativa.is_(True))
        )
        or 0,
        lotes_por_status=lotes_por_status,
        resgates_por_status=resgates_por_status,
        kg_ofertados=round(kg_ofertados, 2),
        kg_resgatados=round(kg_resgatados, 2),
        taxa_aproveitamento=round(kg_resgatados / kg_ofertados, 4) if kg_ofertados else 0.0,
        refeicoes_estimadas=int(kg_resgatados / settings.kg_per_meal),
    )
