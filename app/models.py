from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import utcnow


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    papel: Mapped[str] = mapped_column(String(20))  # doador | ong | admin
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    doador: Mapped[Optional["Doador"]] = relationship(
        back_populates="usuario", uselist=False, cascade="all, delete-orphan"
    )
    instituicao: Mapped[Optional["Instituicao"]] = relationship(
        back_populates="usuario", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def doador_id(self) -> Optional[int]:
        return self.doador.id if self.doador else None

    @property
    def instituicao_id(self) -> Optional[int]:
        return self.instituicao.id if self.instituicao else None


class Doador(Base):
    __tablename__ = "doadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    endereco: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    usuario: Mapped[Usuario] = relationship(back_populates="doador")
    lotes: Mapped[list["Lote"]] = relationship(
        back_populates="doador", cascade="all, delete-orphan"
    )


class Instituicao(Base):
    __tablename__ = "instituicoes"
    __table_args__ = (CheckConstraint("capacidade_kg > 0", name="ck_instituicao_capacidade"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    capacidade_kg: Mapped[float] = mapped_column(Float)  # quanto consegue receber por resgate
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    usuario: Mapped[Usuario] = relationship(back_populates="instituicao")
    resgates: Mapped[list["Resgate"]] = relationship(
        back_populates="instituicao", cascade="all, delete-orphan"
    )


class Lote(Base):
    __tablename__ = "lotes_excedentes"
    __table_args__ = (CheckConstraint("quantidade_kg > 0", name="ck_lote_quantidade"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    doador_id: Mapped[int] = mapped_column(
        ForeignKey("doadores.id", ondelete="CASCADE"), index=True
    )
    descricao: Mapped[str] = mapped_column(String(255))
    categoria: Mapped[str] = mapped_column(String(40))
    quantidade_kg: Mapped[float] = mapped_column(Float)
    disponivel_ate: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="disponivel", index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    doador: Mapped[Doador] = relationship(back_populates="lotes")
    resgates: Mapped[list["Resgate"]] = relationship(
        back_populates="lote", cascade="all, delete-orphan"
    )


class Resgate(Base):
    __tablename__ = "resgates"
    __table_args__ = (UniqueConstraint("lote_id", "instituicao_id", name="uq_resgate_lote_instituicao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(
        ForeignKey("lotes_excedentes.id", ondelete="CASCADE"), index=True
    )
    instituicao_id: Mapped[int] = mapped_column(
        ForeignKey("instituicoes.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="notificado", index=True)
    nota: Mapped[float] = mapped_column(Float, default=0.0)  # índice de compatibilidade (0 a 1)
    webhook_status: Mapped[str] = mapped_column(String(20), default="pendente")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    lote: Mapped[Lote] = relationship(back_populates="resgates")
    instituicao: Mapped[Instituicao] = relationship(back_populates="resgates")
