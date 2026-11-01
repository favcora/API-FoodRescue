"""Cache HTTP: ETag + Cache-Control, com resposta 304 quando o cliente já tem a versão atual."""
import hashlib
import json

from fastapi import Request, Response


def resposta_com_etag(request: Request, conteudo: dict, max_age: int = 30) -> Response:
    corpo = json.dumps(conteudo, sort_keys=True, ensure_ascii=False, default=str).encode()
    etag = '"' + hashlib.sha256(corpo).hexdigest()[:32] + '"'
    cabecalhos = {"ETag": etag, "Cache-Control": f"private, max-age={max_age}"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cabecalhos)
    return Response(content=corpo, media_type="application/json", headers=cabecalhos)
