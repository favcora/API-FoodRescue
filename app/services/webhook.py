"""Envio do webhook de alerta para a instituição mais compatível."""
import hashlib
import hmac
import json

import httpx

from app.config import settings
from app.models import Instituicao, Lote, Resgate
from app.utils import utcnow


def montar_payload(resgate: Resgate, lote: Lote, instituicao: Instituicao, avaliacao: dict) -> dict:
    href = f"/api/v1/resgates/{resgate.id}"
    return {
        "evento": "lote.compativel",
        "enviado_em": utcnow().isoformat() + "Z",
        "resgate": {
            "id": resgate.id,
            "nota": resgate.nota,
            # Links das próximas ações (estilo HATEOAS): a ONG só precisa chamar um deles.
            "acoes": {
                "aceitar": {"metodo": "PATCH", "href": href, "corpo": {"status": "aceito"}},
                "recusar": {"metodo": "PATCH", "href": href, "corpo": {"status": "recusado"}},
            },
        },
        "lote": {
            "id": lote.id,
            "descricao": lote.descricao,
            "categoria": lote.categoria,
            "quantidade_kg": lote.quantidade_kg,
            "disponivel_ate": lote.disponivel_ate.isoformat() + "Z",
        },
        "instituicao": {"id": instituicao.id, "nome": instituicao.nome},
        "compatibilidade": {
            "nota": avaliacao["nota"],
            "distancia_km": avaliacao["distancia_km"],
            "fator_capacidade": avaliacao["fator_capacidade"],
            "fator_distancia": avaliacao["fator_distancia"],
        },
    }


def assinar(corpo: bytes, segredo: str) -> str:
    return hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


def send_webhook(instituicao: Instituicao, payload: dict) -> str:
    """Retorna 'enviado', 'falhou' ou 'sem_webhook'."""
    if not instituicao.webhook_url:
        return "sem_webhook"

    corpo = json.dumps(payload, ensure_ascii=False).encode()
    cabecalhos = {"Content-Type": "application/json", "X-FoodRescue-Event": payload["evento"]}
    if settings.webhook_secret:
        cabecalhos["X-FoodRescue-Signature"] = "sha256=" + assinar(corpo, settings.webhook_secret)

    try:
        resposta = httpx.post(
            instituicao.webhook_url, content=corpo, headers=cabecalhos, timeout=settings.webhook_timeout
        )
    except httpx.HTTPError:
        return "falhou"
    return "enviado" if resposta.status_code < 400 else "falhou"
