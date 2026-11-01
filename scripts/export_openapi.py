"""Exporta a especificação OpenAPI para docs/openapi.json (pode ser importada no Postman/Insomnia).

Uso (na raiz do projeto):  python -m scripts.export_openapi
"""
import json
from pathlib import Path

from app.main import app

destino = Path("docs/openapi.json")
destino.parent.mkdir(exist_ok=True)
destino.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OpenAPI salvo em {destino}")
