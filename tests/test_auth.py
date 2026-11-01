from tests.helpers import SENHA, registrar_doador, registrar_ong


def test_cadastro_e_login_com_sucesso(client):
    usuario = registrar_doador(client)
    assert usuario["papel"] == "doador"
    assert usuario["doador_id"] is not None

    r = client.post("/api/v1/tokens", json={"email": "doador@teste.com", "senha": SENHA})
    assert r.status_code == 201
    token = r.json()["access_token"]

    me = client.get("/api/v1/usuarios/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "doador@teste.com"


def test_email_duplicado_retorna_409(client):
    registrar_ong(client, email="repetido@teste.com")
    r = client.post(
        "/api/v1/usuarios",
        json={
            "email": "repetido@teste.com",
            "senha": SENHA,
            "papel": "doador",
            "perfil_doador": {"nome": "Outra", "latitude": 0, "longitude": 0},
        },
    )
    assert r.status_code == 409
    assert r.json()["erro"]["codigo"] == "CONFLITO"


def test_nao_permite_cadastrar_admin(client):
    r = client.post("/api/v1/usuarios", json={"email": "x@teste.com", "senha": SENHA, "papel": "admin"})
    assert r.status_code == 403


def test_login_com_senha_errada_retorna_401(client):
    registrar_doador(client)
    r = client.post("/api/v1/tokens", json={"email": "doador@teste.com", "senha": "errada123"})
    assert r.status_code == 401
    assert r.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


def test_rota_protegida_sem_token_retorna_401(client):
    r = client.get("/api/v1/lotes-excedentes")
    assert r.status_code == 401
    assert r.json()["erro"]["codigo"] == "NAO_AUTENTICADO"


def test_token_invalido_retorna_401(client):
    r = client.get("/api/v1/lotes-excedentes", headers={"Authorization": "Bearer token-falso"})
    assert r.status_code == 401
    assert r.json()["erro"]["codigo"] == "TOKEN_INVALIDO"


def test_validacao_retorna_400_com_corpo_padronizado(client):
    r = client.post(
        "/api/v1/usuarios",
        json={"email": "email-invalido", "senha": "123", "papel": "doador"},
    )
    assert r.status_code == 400
    erro = r.json()["erro"]
    assert erro["codigo"] == "VALIDACAO"
    assert erro["mensagem"]
    campos = {d["campo"] for d in erro["detalhes"]}
    assert "email" in campos and "senha" in campos
