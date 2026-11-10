# Publicação

API e front ficam em dois projetos da Vercel, e o banco é um Postgres gerenciado (Neon).

## Variáveis da API

| Variável | Valor |
|---|---|
| `DATABASE_URL` | URL do Postgres, de preferência a do pooler |
| `SECRET_KEY` | `openssl rand -hex 32`. Trocar derruba todas as sessões |
| `CORS_ORIGINS` | URL pública do front |
| `AI_PROVIDER` | `gemini` (padrão); um nome desconhecido deixa a IA em 503 e registra o erro no log |
| `GEMINI_API_KEY` | chave da Gemini; sem ela a tela continua no modo manual |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `TRUST_PROXY_HEADERS` | `true`: a Vercel sobrescreve o `X-Forwarded-For` |
| `DB_NULL_POOL` | `true`: em serverless quem faz o pool é o banco |

Nunca ligue `TRUST_PROXY_HEADERS` em servidor exposto direto: o cliente poderia forjar o IP e escapar
do rate limit.

## Variável do front

`VITE_API_URL` com a URL pública da API, definida antes do build.

## Migrations

A função serverless não roda migrations, e o `.vercelignore` nem as envia. Rode da sua máquina **antes**
de publicar uma versão que muda o banco:

```bash
DATABASE_URL='<url direta do banco>' alembic upgrade head
```

## Primeiro admin

Roda uma vez na vida do sistema. Pergunta e-mail, nome e senha no terminal, e a senha não fica no
histórico:

```bash
DATABASE_URL='<url do banco>' SECRET_KEY=x python scripts/seed_admin.py
```

Depois disso, todo o resto se faz pela tela: ministérios, convites e papéis.

## Depois de publicar

- `GET /health/db` responde `{"database": "ok"}`.
- `POST /events/{id}/program/suggest` responde 503 quando a Gemini falha; o motivo fica nos logs.
- **Backup:** o histórico do plano gratuito do Neon é curto. Antes de a igreja depender do sistema,
  agende um `pg_dump` diário ou suba de plano.
- **Rate limit:** a contagem fica em memória, por instância. Em serverless ela freia um ataque, mas não
  garante o limite exato.
