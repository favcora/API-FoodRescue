from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.errors import instalar_handlers
from app.models import Usuario
from app.routers import auth, doadores, instituicoes, lotes, metricas, resgates
from app.security import hash_password


def _criar_admin_inicial() -> None:
    if not (settings.admin_email and settings.admin_password):
        return
    with SessionLocal() as db:
        email = settings.admin_email.lower()
        if db.scalar(select(Usuario).where(Usuario.email == email)) is None:
            db.add(Usuario(email=email, senha_hash=hash_password(settings.admin_password), papel="admin"))
            db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    _criar_admin_inicial()
    yield


DESCRICAO = """
API REST que **redistribui excedentes alimentares**: restaurantes, padarias e cantinas publicam lotes
de comida em bom estado, e a API avisa (via **webhook**) a instituição de solidariedade mais compatível.

**Diferencial:** em vez de só guardar doações, a API calcula um *índice de compatibilidade* entre o lote e
cada instituição (capacidade + distância) e dispara o alerta em tempo real para a melhor. Se ela recusar,
a próxima da fila é notificada automaticamente.

**Autenticação:** crie um usuário em `POST /api/v1/usuarios`, gere o token em `POST /api/v1/tokens` e
clique em **Authorize**. Papéis: `doador`, `ong` e `admin`. Horários em UTC.
"""

TAGS = [
    {"name": "Autenticação", "description": "Cadastro e login (JWT)."},
    {"name": "Doadores", "description": "Restaurantes, padarias e cantinas que doam."},
    {"name": "Instituições", "description": "ONGs que recebem as doações."},
    {"name": "Lotes excedentes", "description": "Comida disponível para resgate + ranking de compatibilidade."},
    {"name": "Resgates", "description": "Ações de recolha: aceitar, recusar, concluir, cancelar."},
    {"name": "Métricas", "description": "Indicadores de impacto (admin)."},
]

app = FastAPI(
    title="Food Rescue API",
    version="1.0.0",
    description=DESCRICAO,
    openapi_tags=TAGS,
    lifespan=lifespan,
)
instalar_handlers(app)

for modulo_router in (
    auth.usuarios,
    auth.tokens,
    doadores.router,
    instituicoes.router,
    lotes.router,
    resgates.router,
    metricas.router,
):
    app.include_router(modulo_router)


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/docs")
