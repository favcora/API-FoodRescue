"""Gera scripts/schema.sql (script de criação do banco) a partir dos modelos.

Uso (na raiz do projeto):  python -m scripts.generate_schema > scripts/schema.sql
"""
from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401  (registra as tabelas)
from app.database import Base

dialeto = sqlite.dialect()
print("-- Food Rescue API: script de criação do banco (SQLite)\n")
for tabela in Base.metadata.sorted_tables:
    print(str(CreateTable(tabela).compile(dialect=dialeto)).strip() + ";\n")
    for indice in tabela.indexes:
        print(str(CreateIndex(indice).compile(dialect=dialeto)).strip() + ";")
    print()
