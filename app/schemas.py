from datetime import datetime
from typing import Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.utils import to_utc_naive, utcnow

Papel = Literal["doador", "ong", "admin"]
CategoriaLote = Literal["refeicoes_prontas", "paes_e_massas", "hortifruti", "laticinios", "outros"]
StatusLote = Literal["disponivel", "reservado", "resgatado", "expirado"]
StatusResgate = Literal["notificado", "aceito", "recusado", "concluido", "cancelado", "expirado"]

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Erros e paginação
class ErroDetalhe(BaseModel):
    campo: Optional[str] = None
    mensagem: str


class ErroCorpo(BaseModel):
    codigo: str
    mensagem: str
    detalhes: list[ErroDetalhe] = []


class ErroOut(BaseModel):
    erro: ErroCorpo


T = TypeVar("T")


class PaginacaoMeta(BaseModel):
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


class PaginacaoLinks(BaseModel):
    atual: str
    proxima: Optional[str] = None
    anterior: Optional[str] = None


class Pagina(BaseModel, Generic[T]):
    dados: list[T]
    paginacao: PaginacaoMeta
    links: PaginacaoLinks


# Autenticação e usuários
class PerfilDoador(BaseModel):
    nome: str = Field(min_length=2, max_length=120, examples=["Padaria "])
    endereco: Optional[str] = Field(default=None, max_length=255)
    latitude: float = Field(ge=-90, le=90, examples=[-9.1383])
    longitude: float = Field(ge=-180, le=180, examples=[-41.1428])


class PerfilInstituicao(BaseModel):
    nome: str = Field(min_length=2, max_length=120, examples=["Casa de Apoio Esperança"])
    capacidade_kg: float = Field(gt=0, le=100000, examples=[80])
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    webhook_url: Optional[HttpUrl] = Field(
        default=None, description="URL que receberá o alerta quando um lote compatível surgir."
    )


class UsuarioCreate(BaseModel):
    email: str = Field(pattern=EMAIL_REGEX, max_length=254, examples=["contato@padaria.com"])
    senha: str = Field(min_length=8, max_length=128)
    papel: Papel
    perfil_doador: Optional[PerfilDoador] = None
    perfil_instituicao: Optional[PerfilInstituicao] = None

    @model_validator(mode="after")
    def _perfil_conforme_papel(self):
        if self.papel == "doador" and self.perfil_doador is None:
            raise ValueError("perfil_doador é obrigatório para o papel 'doador'.")
        if self.papel == "ong" and self.perfil_instituicao is None:
            raise ValueError("perfil_instituicao é obrigatório para o papel 'ong'.")
        return self


class UsuarioOut(ORMModel):
    id: int
    email: str
    papel: Papel
    doador_id: Optional[int] = None
    instituicao_id: Optional[int] = None
    criado_em: datetime


class TokenIn(BaseModel):
    email: str
    senha: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Validade do token em segundos.")


# ---------- Doadores ----------
class DoadorOut(ORMModel):
    id: int
    nome: str
    endereco: Optional[str]
    latitude: float
    longitude: float
    criado_em: datetime


class DoadorUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=120)
    endereco: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


# ---------- Instituições ----------
class InstituicaoOut(ORMModel):
    id: int
    nome: str
    capacidade_kg: float
    latitude: float
    longitude: float
    ativa: bool
    webhook_url: Optional[str] = Field(
        default=None, description="Visível apenas para a própria instituição e para o admin."
    )
    criado_em: datetime


class InstituicaoUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=120)
    capacidade_kg: Optional[float] = Field(default=None, gt=0, le=100000)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    webhook_url: Optional[HttpUrl] = None
    ativa: Optional[bool] = None


# ---------- Lotes ----------
def _data_futura(valor: Optional[datetime]) -> Optional[datetime]:
    if valor is None:
        return None
    valor = to_utc_naive(valor)
    if valor <= utcnow():
        raise ValueError("disponivel_ate deve estar no futuro (horário UTC se não houver fuso).")
    return valor


class LoteCreate(BaseModel):
    descricao: str = Field(min_length=3, max_length=255, examples=["30 marmitas de arroz, feijão e frango"])
    categoria: CategoriaLote
    quantidade_kg: float = Field(gt=0, le=5000, examples=[15])
    disponivel_ate: datetime = Field(description="Até quando a comida pode ser retirada.")

    _validar_data = field_validator("disponivel_ate")(_data_futura)


class LoteUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=3, max_length=255)
    categoria: Optional[CategoriaLote] = None
    quantidade_kg: Optional[float] = Field(default=None, gt=0, le=5000)
    disponivel_ate: Optional[datetime] = None

    _validar_data = field_validator("disponivel_ate")(_data_futura)


class LoteOut(ORMModel):
    id: int
    doador_id: int
    descricao: str
    categoria: CategoriaLote
    quantidade_kg: float
    disponivel_ate: datetime
    status: StatusLote
    criado_em: datetime


class NotificacaoOut(BaseModel):
    resgate_id: int
    instituicao_id: int
    nota: float
    webhook_status: str


class LoteCriadoOut(LoteOut):
    notificacao: Optional[NotificacaoOut] = Field(
        default=None,
        description="Instituição mais compatível que foi notificada (nulo se nenhuma estiver ao alcance).",
    )


class CompatibilidadeOut(BaseModel):
    instituicao_id: int
    nome: str
    capacidade_kg: float
    distancia_km: float
    fator_capacidade: float
    fator_distancia: float
    nota: float = Field(description="Índice de compatibilidade de 0 a 1.")


# Resgates 
class ResgateCreate(BaseModel):
    lote_id: int


class ResgateUpdate(BaseModel):
    status: Literal["aceito", "recusado", "concluido", "cancelado"]


class ResgateOut(ORMModel):
    id: int
    lote_id: int
    instituicao_id: int
    status: StatusResgate
    nota: float
    webhook_status: str
    criado_em: datetime
    atualizado_em: datetime


# Métricas
class MetricasImpactoOut(BaseModel):
    doadores_cadastrados: int
    instituicoes_ativas: int
    lotes_por_status: dict[str, int]
    resgates_por_status: dict[str, int]
    kg_ofertados: float
    kg_resgatados: float
    taxa_aproveitamento: float = Field(description="kg resgatados ÷ kg ofertados (0 a 1).")
    refeicoes_estimadas: int = Field(description="Estimativa: 1 refeição ≈ 0,5 kg.")
