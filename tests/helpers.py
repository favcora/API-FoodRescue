from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Usuario
from app.security import hash_password

# Paulistana (PI), usada como ponto de partida
LAT, LON = -9.1383, -41.1428
SENHA = "senha1234"


def registrar_doador(client, email="doador@teste.com", lat=LAT, lon=LON):
    r = client.post(
        "/api/v1/usuarios",
        json={
            "email": email,
            "senha": SENHA,
            "papel": "doador",
            "perfil_doador": {"nome": "Padaria Central", "latitude": lat, "longitude": lon},
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def registrar_ong(client, email="ong@teste.com", lat=LAT + 0.01, lon=LON, capacidade_kg=100,
                  webhook_url="https://example.org/hook"):
    r = client.post(
        "/api/v1/usuarios",
        json={
            "email": email,
            "senha": SENHA,
            "papel": "ong",
            "perfil_instituicao": {
                "nome": f"ONG {email}",
                "capacidade_kg": capacidade_kg,
                "latitude": lat,
                "longitude": lon,
                "webhook_url": webhook_url,
            },
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def criar_admin(email="admin@teste.com"):
    with SessionLocal() as db:
        db.add(Usuario(email=email, senha_hash=hash_password(SENHA), papel="admin"))
        db.commit()


def login(client, email):
    r = client.post("/api/v1/tokens", json={"email": email, "senha": SENHA})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def corpo_lote(quantidade_kg=50, categoria="refeicoes_prontas", horas=6):
    prazo = datetime.now(timezone.utc) + timedelta(hours=horas)
    return {
        "descricao": "Marmitas do almoço que sobraram",
        "categoria": categoria,
        "quantidade_kg": quantidade_kg,
        "disponivel_ate": prazo.isoformat(),
    }


def criar_lote(client, headers, **kwargs):
    r = client.post("/api/v1/lotes-excedentes", json=corpo_lote(**kwargs), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
