from tests.helpers import (
    LAT,
    LON,
    corpo_lote,
    criar_lote,
    login,
    registrar_doador,
    registrar_ong,
)


def test_lote_criado_notifica_a_ong_mais_compativel(client, webhooks):
    registrar_doador(client)
    perto = registrar_ong(client, email="perto@teste.com", lat=LAT + 0.01, capacidade_kg=100)
    registrar_ong(client, email="longe@teste.com", lat=LAT + 0.2, capacidade_kg=100)
    headers = login(client, "doador@teste.com")

    lote = criar_lote(client, headers, quantidade_kg=50)

    assert lote["status"] == "disponivel"
    assert lote["notificacao"]["instituicao_id"] == perto["instituicao_id"]
    assert lote["notificacao"]["webhook_status"] == "enviado"
    assert len(webhooks) == 1
    instituicao_id, payload = webhooks[0]
    assert instituicao_id == perto["instituicao_id"]
    assert payload["evento"] == "lote.compativel"
    assert payload["resgate"]["acoes"]["aceitar"]["metodo"] == "PATCH"


def test_ranking_de_compatibilidade_considera_capacidade_e_distancia(client):
    registrar_doador(client)
    a = registrar_ong(client, email="a@teste.com", lat=LAT + 0.01, capacidade_kg=100)  # perto e cabe tudo
    b = registrar_ong(client, email="b@teste.com", lat=LAT + 0.01, capacidade_kg=10)  # perto, mas não cabe
    c = registrar_ong(client, email="c@teste.com", lat=LAT + 0.2, capacidade_kg=100)  # longe, cabe tudo
    registrar_ong(client, email="d@teste.com", lat=LAT + 1.0, capacidade_kg=100)  # fora do alcance (>30 km)
    headers = login(client, "doador@teste.com")
    lote = criar_lote(client, headers, quantidade_kg=50)

    r = client.get(f"/api/v1/lotes-excedentes/{lote['id']}/compatibilidades", headers=headers)
    assert r.status_code == 200
    ranking = r.json()
    ordem = [item["instituicao_id"] for item in ranking]
    assert ordem == [a["instituicao_id"], c["instituicao_id"], b["instituicao_id"]]
    notas = [item["nota"] for item in ranking]
    assert notas == sorted(notas, reverse=True)
    assert all(0 <= n <= 1 for n in notas)


def test_lote_sem_instituicoes_ao_alcance_nao_gera_notificacao(client, webhooks):
    registrar_doador(client)
    headers = login(client, "doador@teste.com")
    lote = criar_lote(client, headers)
    assert lote["notificacao"] is None
    assert webhooks == []


def test_ong_nao_pode_criar_lote(client):
    registrar_ong(client)
    headers = login(client, "ong@teste.com")
    r = client.post("/api/v1/lotes-excedentes", json=corpo_lote(), headers=headers)
    assert r.status_code == 403
    assert r.json()["erro"]["codigo"] == "ACESSO_NEGADO"


def test_doador_nao_ve_lote_de_outro_doador(client):
    registrar_doador(client, email="d1@teste.com")
    registrar_doador(client, email="d2@teste.com", lat=LAT, lon=LON)
    h1 = login(client, "d1@teste.com")
    h2 = login(client, "d2@teste.com")
    lote = criar_lote(client, h1)

    r = client.get(f"/api/v1/lotes-excedentes/{lote['id']}", headers=h2)
    assert r.status_code == 403
    lista = client.get("/api/v1/lotes-excedentes", headers=h2).json()
    assert lista["paginacao"]["total"] == 0


def test_paginacao_filtro_e_ordenacao(client):
    registrar_doador(client)
    headers = login(client, "doador@teste.com")
    for kg in (10, 20, 30, 40, 50):
        criar_lote(client, headers, quantidade_kg=kg, categoria="hortifruti" if kg >= 40 else "outros")

    pag1 = client.get(
        "/api/v1/lotes-excedentes?tamanho_pagina=2&pagina=1&ordenar=-quantidade_kg", headers=headers
    ).json()
    assert pag1["paginacao"] == {"pagina": 1, "tamanho_pagina": 2, "total": 5, "total_paginas": 3}
    assert [l["quantidade_kg"] for l in pag1["dados"]] == [50, 40]
    assert pag1["links"]["proxima"] is not None and pag1["links"]["anterior"] is None

    pag3 = client.get(
        "/api/v1/lotes-excedentes?tamanho_pagina=2&pagina=3&ordenar=-quantidade_kg", headers=headers
    ).json()
    assert [l["quantidade_kg"] for l in pag3["dados"]] == [10]
    assert pag3["links"]["proxima"] is None

    filtrados = client.get("/api/v1/lotes-excedentes?categoria=hortifruti", headers=headers).json()
    assert filtrados["paginacao"]["total"] == 2

    faixa = client.get(
        "/api/v1/lotes-excedentes?quantidade_min=20&quantidade_max=30", headers=headers
    ).json()
    assert faixa["paginacao"]["total"] == 2

    ruim = client.get("/api/v1/lotes-excedentes?ordenar=campo_que_nao_existe", headers=headers)
    assert ruim.status_code == 400


def test_quantidade_negativa_retorna_400(client):
    registrar_doador(client)
    headers = login(client, "doador@teste.com")
    r = client.post("/api/v1/lotes-excedentes", json=corpo_lote(quantidade_kg=-5), headers=headers)
    assert r.status_code == 400
    assert r.json()["erro"]["codigo"] == "VALIDACAO"


def test_prazo_no_passado_retorna_400(client):
    registrar_doador(client)
    headers = login(client, "doador@teste.com")
    r = client.post("/api/v1/lotes-excedentes", json=corpo_lote(horas=-2), headers=headers)
    assert r.status_code == 400


def test_lote_inexistente_retorna_404_padronizado(client):
    registrar_doador(client)
    headers = login(client, "doador@teste.com")
    r = client.get("/api/v1/lotes-excedentes/9999", headers=headers)
    assert r.status_code == 404
    assert r.json()["erro"]["codigo"] == "NAO_ENCONTRADO"


def test_atualizar_e_remover_lote_disponivel(client):
    registrar_doador(client)
    headers = login(client, "doador@teste.com")
    lote = criar_lote(client, headers, quantidade_kg=10)

    r = client.patch(f"/api/v1/lotes-excedentes/{lote['id']}", json={"quantidade_kg": 12}, headers=headers)
    assert r.status_code == 200
    assert r.json()["quantidade_kg"] == 12

    assert client.delete(f"/api/v1/lotes-excedentes/{lote['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/lotes-excedentes/{lote['id']}", headers=headers).status_code == 404


def test_cache_etag_retorna_304(client):
    registrar_doador(client)
    ong = registrar_ong(client)
    headers = login(client, "doador@teste.com")

    url = f"/api/v1/instituicoes/{ong['instituicao_id']}"
    primeira = client.get(url, headers=headers)
    assert primeira.status_code == 200
    assert "max-age" in primeira.headers["cache-control"]
    etag = primeira.headers["etag"]

    segunda = client.get(url, headers={**headers, "If-None-Match": etag})
    assert segunda.status_code == 304
    assert primeira.json()["webhook_url"] is None
