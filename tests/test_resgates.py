from tests.helpers import (
    LAT,
    criar_admin,
    criar_lote,
    login,
    registrar_doador,
    registrar_ong,
)


def test_fluxo_completo_do_resgate_e_metricas(client):
    registrar_doador(client)
    registrar_ong(client)
    criar_admin()
    h_doador = login(client, "doador@teste.com")
    h_ong = login(client, "ong@teste.com")
    h_admin = login(client, "admin@teste.com")

    lote = criar_lote(client, h_doador, quantidade_kg=40)
    resgate_id = lote["notificacao"]["resgate_id"]

    r = client.get(f"/api/v1/resgates/{resgate_id}", headers=h_ong)
    assert r.json()["status"] == "notificado"

    r = client.patch(f"/api/v1/resgates/{resgate_id}", json={"status": "aceito"}, headers=h_ong)
    assert r.status_code == 200 and r.json()["status"] == "aceito"
    assert client.get(f"/api/v1/lotes-excedentes/{lote['id']}", headers=h_doador).json()["status"] == "reservado"

    r = client.patch(f"/api/v1/resgates/{resgate_id}", json={"status": "concluido"}, headers=h_ong)
    assert r.status_code == 200 and r.json()["status"] == "concluido"
    assert client.get(f"/api/v1/lotes-excedentes/{lote['id']}", headers=h_doador).json()["status"] == "resgatado"

    metricas = client.get("/api/v1/metricas/impacto", headers=h_admin)
    assert metricas.status_code == 200
    dados = metricas.json()
    assert dados["kg_resgatados"] == 40
    assert dados["taxa_aproveitamento"] == 1.0
    assert dados["refeicoes_estimadas"] == 80
    assert dados["lotes_por_status"]["resgatado"] == 1


def test_transicao_invalida_retorna_409(client):
    registrar_doador(client)
    registrar_ong(client)
    h_doador = login(client, "doador@teste.com")
    h_ong = login(client, "ong@teste.com")
    lote = criar_lote(client, h_doador)

    r = client.patch(
        f"/api/v1/resgates/{lote['notificacao']['resgate_id']}", json={"status": "concluido"}, headers=h_ong
    )
    assert r.status_code == 409
    assert r.json()["erro"]["codigo"] == "CONFLITO"


def test_recusa_notifica_a_proxima_instituicao(client, webhooks):
    registrar_doador(client)
    perto = registrar_ong(client, email="perto@teste.com", lat=LAT + 0.01)
    longe = registrar_ong(client, email="longe@teste.com", lat=LAT + 0.2)
    h_doador = login(client, "doador@teste.com")
    h_perto = login(client, "perto@teste.com")
    h_longe = login(client, "longe@teste.com")

    lote = criar_lote(client, h_doador)
    assert lote["notificacao"]["instituicao_id"] == perto["instituicao_id"]

    r = client.patch(
        f"/api/v1/resgates/{lote['notificacao']['resgate_id']}", json={"status": "recusado"}, headers=h_perto
    )
    assert r.status_code == 200

    assert [chamada[0] for chamada in webhooks] == [perto["instituicao_id"], longe["instituicao_id"]]
    pendentes = client.get("/api/v1/resgates?status=notificado", headers=h_longe).json()
    assert pendentes["paginacao"]["total"] == 1


def test_outra_ong_nao_pode_alterar_resgate(client):
    registrar_doador(client)
    registrar_ong(client, email="dona@teste.com")
    registrar_ong(client, email="intrusa@teste.com", lat=LAT + 0.5)
    h_doador = login(client, "doador@teste.com")
    h_intrusa = login(client, "intrusa@teste.com")
    lote = criar_lote(client, h_doador)

    r = client.patch(
        f"/api/v1/resgates/{lote['notificacao']['resgate_id']}", json={"status": "aceito"}, headers=h_intrusa
    )
    assert r.status_code == 403


def test_lote_reservado_nao_pode_ser_excluido(client):
    registrar_doador(client)
    registrar_ong(client)
    h_doador = login(client, "doador@teste.com")
    h_ong = login(client, "ong@teste.com")
    lote = criar_lote(client, h_doador)
    client.patch(f"/api/v1/resgates/{lote['notificacao']['resgate_id']}", json={"status": "aceito"}, headers=h_ong)

    r = client.delete(f"/api/v1/lotes-excedentes/{lote['id']}", headers=h_doador)
    assert r.status_code == 409


def test_ong_solicita_resgate_direto_e_segunda_ong_recebe_409(client):
    registrar_doador(client)
    registrar_ong(client, email="primeira@teste.com")
    registrar_ong(client, email="segunda@teste.com", lat=LAT + 0.05)
    h_doador = login(client, "doador@teste.com")
    h_primeira = login(client, "primeira@teste.com")
    h_segunda = login(client, "segunda@teste.com")
    lote = criar_lote(client, h_doador)

    r = client.post("/api/v1/resgates", json={"lote_id": lote["id"]}, headers=h_segunda)
    assert r.status_code == 201
    assert r.json()["status"] == "aceito"
    assert r.headers["location"].startswith("/api/v1/resgates/")

    # o alerta aberto da primeira ONG expirou e o lote já está reservado
    r = client.post("/api/v1/resgates", json={"lote_id": lote["id"]}, headers=h_primeira)
    assert r.status_code == 409


def test_metricas_apenas_para_admin(client):
    registrar_doador(client)
    criar_admin()
    assert client.get("/api/v1/metricas/impacto", headers=login(client, "doador@teste.com")).status_code == 403
    assert client.get("/api/v1/metricas/impacto", headers=login(client, "admin@teste.com")).status_code == 200


def test_admin_remove_resgate_encerrado(client):
    registrar_doador(client)
    registrar_ong(client)
    criar_admin()
    h_doador = login(client, "doador@teste.com")
    h_ong = login(client, "ong@teste.com")
    h_admin = login(client, "admin@teste.com")
    lote = criar_lote(client, h_doador)
    resgate_id = lote["notificacao"]["resgate_id"]

    # ainda notificado: não pode remover
    assert client.delete(f"/api/v1/resgates/{resgate_id}", headers=h_admin).status_code == 409
    client.patch(f"/api/v1/resgates/{resgate_id}", json={"status": "recusado"}, headers=h_ong)
    assert client.delete(f"/api/v1/resgates/{resgate_id}", headers=h_admin).status_code == 204
    assert client.get(f"/api/v1/resgates/{resgate_id}", headers=h_admin).status_code == 404
