import re

import pytest

from app.main import app
from app.services.compatibilidade import calcular_nota, fator_capacidade, fator_distancia
from app.services.geo import haversine_km
from app.services.webhook import assinar


def test_haversine_mesmo_ponto_e_um_grau_de_latitude():
    assert haversine_km(-9.0, -41.0, -9.0, -41.0) == 0
    assert haversine_km(0, 0, 1, 0) == pytest.approx(111.2, abs=0.5)


def test_fatores_de_capacidade_e_distancia():
    assert fator_capacidade(100, 50) == 1.0  # cabe tudo: limitado a 1
    assert fator_capacidade(25, 50) == 0.5
    assert fator_distancia(0, 30) == 1.0
    assert fator_distancia(15, 30) == 0.5
    assert fator_distancia(60, 30) == 0.0  # nunca negativo


def test_nota_de_compatibilidade_usa_pesos_60_40():
    assert calcular_nota(1.0, 1.0, peso_capacidade=0.6) == 1.0
    assert calcular_nota(1.0, 0.0, peso_capacidade=0.6) == 0.6
    assert calcular_nota(0.0, 1.0, peso_capacidade=0.6) == 0.4


def test_assinatura_do_webhook_e_deterministica():
    corpo = b'{"evento":"lote.compativel"}'
    assert assinar(corpo, "segredo") == assinar(corpo, "segredo")
    assert assinar(corpo, "segredo") != assinar(corpo, "outro-segredo")
    assert len(assinar(corpo, "segredo")) == 64


def test_uris_seguem_a_nomenclatura_do_enunciado():
    """Substantivos no plural, minúsculas, hifens e nenhum verbo na URI."""
    segmento = re.compile(r"^([a-z0-9]+(-[a-z0-9]+)*|\{[a-z_]+\})$")
    verbos = {"criar", "listar", "buscar", "remover", "deletar", "atualizar", "login", "get", "create", "delete", "update"}
    caminhos = [p for p in app.openapi()["paths"] if p.startswith("/api/v1")]
    assert caminhos
    for caminho in caminhos:
        partes = caminho.strip("/").split("/")
        assert partes[:2] == ["api", "v1"]
        for parte in partes[2:]:
            assert segmento.match(parte), f"URI fora do padrão: {caminho}"
            assert parte not in verbos, f"Verbo na URI: {caminho}"
