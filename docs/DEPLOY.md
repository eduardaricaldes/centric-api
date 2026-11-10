# Publicação

API e front ficam em dois projetos da Vercel, e o banco é um Postgres gerenciado (Neon).

## Variáveis da API

| Variável | Valor |
|---|---|
| `DATABASE_URL` | URL do Postgres, de preferência a do pooler |
| `SECRET_KEY` | `openssl rand -hex 32`. Trocar derruba todas as sessões |
| `CORS_ORIGINS` | URL pública do front |
| `GEMINI_API_KEY` | chave da Gemini (Google AI Studio, plano gratuito) |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `GROQ_API_KEY` | opcional: chave gratuita do Groq (console.groq.com), 3º degrau da IA |
| `OPENROUTER_API_KEY` | opcional: chave gratuita do OpenRouter (openrouter.ai), 4º degrau da IA |
| `TRUST_PROXY_HEADERS` | `true`: a Vercel sobrescreve o `X-Forwarded-For` |
| `DB_NULL_POOL` | `true`: em serverless quem faz o pool é o banco |

As variáveis abaixo já têm padrão no código; só cadastre na Vercel se quiser trocar:

| Variável | Padrão |
|---|---|
| `AI_PROVIDER` | `gemini,groq,openrouter`: ordem da cadeia; nome desconhecido é ignorado com erro no log |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.1-flash-lite`; vazio desliga |
| `GEMINI_TIMEOUT_SECONDS` | `30` |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `OPENROUTER_MODEL` | `nvidia/nemotron-3.5-super-vl:free`; modelo sem `:free` tira o OpenRouter da cadeia |
| `AI_FALLBACK_TIMEOUT_SECONDS` | `20` (Groq e OpenRouter) |

### Sugestão por IA (só planos gratuitos)

`POST /events/{id}/program/suggest` tenta, em ordem: `GEMINI_MODEL` → `GEMINI_FALLBACK_MODEL` → Groq →
OpenRouter. Um provedor sem chave é pulado. Passa para o próximo em 429 (cota), 5xx, timeout, erro de rede
ou resposta que não vira uma programação válida. Se todos falharem, responde 503 e a tela fica no modo
manual. O `provider_model` da sugestão diz quem respondeu (por exemplo `groq:openai/gpt-oss-120b`).

Para continuar sem custo: não cadastre cartão nem ative billing no Google AI Studio e no Groq, e no
OpenRouter use só modelos `:free`. A lista de modelos gratuitos do OpenRouter muda com frequência; se o
modelo padrão sumir, escolha outro em `https://openrouter.ai/api/v1/models` que termine em `:free` e tenha
`structured_outputs` em `supported_parameters`.

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
- `POST /events/{id}/program/suggest` responde 503 quando todos os provedores de IA falham; o motivo fica nos logs.
- **Backup:** o histórico do plano gratuito do Neon é curto. Antes de a igreja depender do sistema,
  agende um `pg_dump` diário ou suba de plano.
- **Rate limit:** a contagem fica em memória, por instância. Em serverless ela freia um ataque, mas não
  garante o limite exato.
