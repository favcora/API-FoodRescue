from math import ceil
from typing import Callable, Optional

from fastapi import Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError


def parametros_paginacao(
    pagina: int = Query(1, ge=1, description="Número da página (começa em 1)."),
    tamanho_pagina: int = Query(10, ge=1, le=100, description="Itens por página (máx. 100)."),
) -> tuple[int, int]:
    return pagina, tamanho_pagina


def aplicar_ordenacao(stmt, modelo, ordenar: Optional[str], permitidos: set[str], padrao: str):
    """`ordenar=campo` (crescente) ou `ordenar=-campo` (decrescente)."""
    campo = ordenar or padrao
    decrescente = campo.startswith("-")
    nome = campo[1:] if decrescente else campo
    if nome not in permitidos:
        raise AppError(
            400,
            "VALIDACAO",
            "Campo de ordenação inválido.",
            [{
                "campo": "ordenar",
                "mensagem": f"Valores aceitos: {', '.join(sorted(permitidos))} (use '-' na frente para ordem decrescente).",
            }],
        )
    coluna = getattr(modelo, nome)
    return stmt.order_by(coluna.desc() if decrescente else coluna.asc(), modelo.id.asc())


def paginar(db: Session, stmt, request: Request, pagina: int, tamanho: int, serializar: Callable) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    itens = db.scalars(stmt.offset((pagina - 1) * tamanho).limit(tamanho)).all()
    total_paginas = ceil(total / tamanho)

    def link(numero: int) -> str:
        return str(request.url.include_query_params(pagina=numero))

    return {
        "dados": [serializar(item) for item in itens],
        "paginacao": {
            "pagina": pagina,
            "tamanho_pagina": tamanho,
            "total": total,
            "total_paginas": total_paginas,
        },
        "links": {
            "atual": link(pagina),
            "proxima": link(pagina + 1) if pagina < total_paginas else None,
            "anterior": link(pagina - 1) if pagina > 1 else None,
        },
    }
