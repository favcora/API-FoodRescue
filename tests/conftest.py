import os
import tempfile

# Configuração de teste: precisa vir ANTES de importar a aplicação.
_pasta = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_pasta}/teste.db"
os.environ["SECRET_KEY"] = "chave-de-teste-com-mais-de-32-caracteres-ok"
os.environ["PASSWORD_ITERATIONS"] = "1000"
os.environ["WEBHOOK_SECRET"] = "segredo-de-teste"
os.environ["MAX_DISTANCE_KM"] = "30"
os.environ["WEIGHT_CAPACITY"] = "0.6"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def banco_limpo():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def webhooks(monkeypatch):
    """Substitui o envio HTTP real: guarda as chamadas para os testes conferirem."""
    chamadas = []

    def falso(instituicao, payload):
        chamadas.append((instituicao.id, payload))
        return "enviado"

    monkeypatch.setattr("app.services.webhook.send_webhook", falso)
    return chamadas
