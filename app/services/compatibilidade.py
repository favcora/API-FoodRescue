"""Regra de negócio inovadora: índice de compatibilidade entre um lote e uma instituição.

    nota = peso_capacidade * fator_capacidade + (1 - peso_capacidade) * fator_distancia

    fator_capacidade = min(capacidade_kg / quantidade_kg, 1)      (1 = a ONG recebe o lote inteiro)
    fator_distancia  = max(0, 1 - distancia_km / MAX_DISTANCE_KM) (1 = bem pertinho)

Instituições inativas ou além de MAX_DISTANCE_KM não participam do ranking.
"""
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Instituicao, Lote
from app.services.geo import haversine_km


def fator_capacidade(capacidade_kg: float, quantidade_kg: float) -> float:
    return min(capacidade_kg / quantidade_kg, 1.0)


def fator_distancia(distancia_km: float, max_distancia_km: float) -> float:
    return max(0.0, 1.0 - distancia_km / max_distancia_km)


def calcular_nota(f_capacidade: float, f_distancia: float, peso_capacidade: Optional[float] = None) -> float:
    peso = settings.weight_capacity if peso_capacidade is None else peso_capacidade
    return round(peso * f_capacidade + (1 - peso) * f_distancia, 4)


def avaliar(lote: Lote, instituicao: Instituicao) -> dict:
    distancia = haversine_km(
        lote.doador.latitude, lote.doador.longitude, instituicao.latitude, instituicao.longitude
    )
    f_cap = fator_capacidade(instituicao.capacidade_kg, lote.quantidade_kg)
    f_dist = fator_distancia(distancia, settings.max_distance_km)
    return {
        "instituicao_id": instituicao.id,
        "nome": instituicao.nome,
        "capacidade_kg": instituicao.capacidade_kg,
        "distancia_km": round(distancia, 2),
        "fator_capacidade": round(f_cap, 4),
        "fator_distancia": round(f_dist, 4),
        "nota": calcular_nota(f_cap, f_dist),
    }


def ranquear_instituicoes(
    db: Session,
    lote: Lote,
    excluir_ids: Iterable[int] = (),
    limite: Optional[int] = None,
) -> list[dict]:
    """Instituições elegíveis ordenadas da mais para a menos compatível."""
    stmt = select(Instituicao).where(Instituicao.ativa.is_(True))
    excluir = list(excluir_ids)
    if excluir:
        stmt = stmt.where(Instituicao.id.not_in(excluir))

    avaliacoes = []
    for instituicao in db.scalars(stmt):
        avaliacao = avaliar(lote, instituicao)
        if avaliacao["distancia_km"] <= settings.max_distance_km:
            avaliacoes.append(avaliacao)

    avaliacoes.sort(key=lambda a: (-a["nota"], a["distancia_km"], a["instituicao_id"]))
    return avaliacoes[:limite] if limite else avaliacoes
