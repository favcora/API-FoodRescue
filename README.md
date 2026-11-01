# Food Rescue API

API RESTful que **redistribui excedentes alimentares**. Restaurantes, padarias e cantinas publicam lotes de comida em bom estado; a API calcula quais instituições de solidariedade são mais compatíveis e **avisa a melhor por webhook**.

## O que a API faz de diferente

A maioria das plataformas de combate ao desperdício só guarda e lista ofertas. Aqui na API decide e avisa

1. O doador publica um lote (`POST /api/v1/lotes-excedentes`).
2. A API calcula o **índice de compatibilidade** de cada ONG ao alcance:

   ```
   nota = 0,6 × fator_capacidade + 0,4 × fator_distancia
   fator_capacidade = min(capacidade_kg ÷ quantidade_kg, 1)
   fator_distancia  = max(0, 1 − distancia_km ÷ 30)
   ```
3. A ONG com a maior nota recebe um **webhook** (`lote.compativel`) com links para aceitar ou recusar.
4. Se ela **recusar** (ou cancelar), a próxima da fila é notificada automaticamente.

Eixos de inovação: **Impacto social** + **Tempo real / eventos**.

## Recursos e endpoints (`/api/v1`)

| Recurso | Endpoints |
|---|---|
| Autenticação | `POST /usuarios` (cadastro) · `GET /usuarios/me` · `POST /tokens` (login) |
| Doadores | `GET /doadores` · `GET/PATCH/DELETE /doadores/{id}` |
| Instituições | `GET /instituicoes` · `GET/PATCH/DELETE /instituicoes/{id}` |
| Lotes excedentes | `GET/POST /lotes-excedentes` · `GET/PATCH/DELETE /lotes-excedentes/{id}` · **`GET /lotes-excedentes/{id}/compatibilidades`** |
| Resgates | `GET/POST /resgates` · `GET/PATCH/DELETE /resgates/{id}` |
| Métricas | `GET /metricas/impacto` |

Listagens aceitam `pagina`, `tamanho_pagina`, `ordenar` (ex.: `-quantidade_kg`) e filtros (ex.: `/lotes-excedentes?status=disponivel&categoria=hortifruti&quantidade_min=10`).

**Fluxo do resgate:** `notificado → aceito | recusado` e `aceito → concluido | cancelado` (via `PATCH /resgates/{id}` com `{"status": "..."}`). Transição inválida retorna `409`.

**Papéis**

| Papel | Pode |
|---|---|
| `doador` | criar/alterar/remover os próprios lotes; ver o ranking e os resgates dos seus lotes |
| `ong` | listar lotes, aceitar/recusar/concluir resgates, solicitar um lote direto, editar a própria instituição (inclusive `webhook_url`) |
| `admin` | tudo acima + métricas de impacto + remover doadores, instituições e resgates encerrados |

O `admin` não pode ser criado por cadastro público: defina `ADMIN_EMAIL` e `ADMIN_PASSWORD` no `.env`.

## Como rodar

Requer Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # Windows: copy .env.example .env  (e edite os valores)

uvicorn app.main:app --reload
```

- Documentação interativa (Swagger): http://localhost:8000/docs
- Especificação OpenAPI: http://localhost:8000/openapi.json (cópia em `docs/openapi.json`)

As tabelas são criadas automaticamente na primeira execução. O script SQL de criação está em `scripts/schema.sql` (gerado com `python -m scripts.generate_schema > scripts/schema.sql`).

### Variáveis de ambiente

| Variável | Para quê | Padrão |
|---|---|---|
| `DATABASE_URL` | banco (SQLite, PostgreSQL...) | `sqlite:///./food_rescue.db` |
| `SECRET_KEY` | assina os tokens JWT | aleatória a cada execução |
| `ACCESS_TOKEN_MINUTES` | validade do token | `60` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | cria o admin inicial | — |
| `WEBHOOK_SECRET` | assinatura HMAC-SHA256 do webhook (cabeçalho `X-FoodRescue-Signature`) | vazio |
| `WEBHOOK_TIMEOUT_SECONDS` | tempo máximo de espera pelo webhook | `3` |
| `MAX_DISTANCE_KM` | raio máximo de busca | `30` |
| `WEIGHT_CAPACITY` | peso da capacidade na nota (distância = 1 − peso) | `0.6` |

## Testando o webhook (demonstração)

1. Abra https://webhook.site e copie a URL única que ele gera.
2. Cadastre uma ONG com essa URL em `perfil_instituicao.webhook_url` (ou use `PATCH /instituicoes/{id}`).
3. Cadastre um doador próximo (até 30 km) e publique um lote.
4. Veja a notificação chegar em tempo real no webhook.site.

## Princípios REST aplicados

- **Cliente-servidor e stateless:** cada requisição leva o próprio token JWT; o servidor não guarda sessão.
- **Cacheable:** `GET /lotes-excedentes/{id}` e `GET /instituicoes/{id}` enviam `ETag` + `Cache-Control` e respondem `304` quando nada mudou.
- **Interface uniforme:** substantivos no plural, minúsculas e hifens; verbos HTTP corretos; `Location` nos `201`; links de paginação e de ações no webhook.
- **Camadas:** rotas (`routers/`) → regras de negócio (`services/`) → banco (`models.py`).
- **Versionamento:** versão na URI (`/api/v1`).
- **Erros padronizados:** `{"erro": {"codigo", "mensagem", "detalhes": []}}` com `400, 401, 403, 404, 409`.

## Estrutura

```
app/
  main.py            # aplicação e documentação OpenAPI
  config.py          # variáveis de ambiente
  models.py          # tabelas (SQLAlchemy)
  schemas.py         # validação de entrada/saída (Pydantic)
  security.py, deps.py   # JWT, senhas e papéis
  errors.py          # formato padronizado de erro
  routers/           # endpoints
  services/          # compatibilidade, webhook, notificação
scripts/             # schema.sql e exportação do OpenAPI
tests/               # pytest
```

## Uso de IA 

Uso do **Claude (Anthropic)** como ferramenta de apoio. Onde e para quê:

Compatibilidade da regra de negócio com a FastAPI 
Auxilio com o esqueleto, autenticação JWT, tratamento de erros e webhook e alguns dos testes para garantir que funcionam

- A distância é em linha reta (fórmula de Haversine), não por rota.
- O webhook é enviado de forma síncrona, sem reenvio automático em caso de falha; o resultado fica registrado em `webhook_status`.
- Usado para testes com apenas dados fictícios ou abertos (LGPD).
- Auxilio de documentação README para melhor esclarecimento
