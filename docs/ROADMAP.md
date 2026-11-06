# Centric — Próximos passos

Documento de planejamento da API do Centric (Comunidade North).
Última atualização: 19/09/2026 (fases 1 a 5 concluídas).

---

## 1. Onde o projeto está hoje

### Pronto e funcionando

| Área | Status |
|---|---|
| Autenticação (registro, login, JWT) | OK |
| CRUD de músicas (`/songs`) | OK, com busca e paginação |
| CRUD de playlists (`/playlist`) | OK |
| Músicas da playlist (`/playlist/{id}/songs`) | OK, com ordenação |
| Controle de acesso ADMIN x USER | Funciona, mas é simples demais (ver fase 3) |
| Testes automatizados | 15 testes em `tests/` |

Isso cobre o **MVP 1** e o **MVP 2** descritos na especificação do projeto.

### Endpoints atuais

```
POST   /auth/register
POST   /auth/login

POST   /songs/                              (admin)
GET    /songs/                              busca por título/artista + paginação
GET    /songs/{song_id}
PUT    /songs/{song_id}                     (admin)
PATCH  /songs/{song_id}                     (admin)
DELETE /songs/{song_id}                     (admin)

POST   /playlist/                           (admin)
GET    /playlist/                           lista paginada
GET    /playlist/{id}                       playlist + músicas + letras, na ordem
PUT    /playlist/{id}                       (admin) atualização parcial
DELETE /playlist/{id}                       (admin) remove a playlist, não as músicas

GET    /playlist/{id}/songs/                músicas do culto, na ordem, com letra
POST   /playlist/{id}/songs/                (admin) adiciona; sem position vai para o fim
PATCH  /playlist/{id}/songs/{item_id}       (admin) move uma música de posição
PUT    /playlist/{id}/songs/reorder         (admin) reordena a playlist inteira
DELETE /playlist/{id}/songs/{item_id}       (admin) tira a música do culto
```

**Decisão de arquitetura:** as rotas de `PlaylistSong` são **aninhadas** (`/playlist/{id}/songs`)
e não uma rota separada `/playlist-songs`. Motivo: um `PlaylistSong` não existe fora de uma
playlist. Com a rota aninhada, toda requisição já valida a playlist e a autorização em um lugar
só, e o front nunca precisa "adivinhar" a qual playlist um item pertence.

### O que ainda incomoda

Na API, nada. As três coisas que estavam anotadas aqui — token de 30 minutos, falta do
`GET /auth/me` e busca vazia devolvendo 404 — foram resolvidas na fase 2, e a dívida técnica antiga
saiu na fase 1.

O que incomoda agora é que **a API está pronta e ninguém da igreja consegue usar**, porque não existe
tela. O próximo passo é o front-end, com os requisitos que já estão escritos no documento separado.

---

## 2. Fase 1 — Fechar a base (concluída)

Antes de crescer, deixar a base sólida:

1. **CORS** em `main.py`, liberando a origem do front.
2. **Seed do primeiro admin** — hoje todo mundo que se registra vira `USER` e não existe forma de
   criar o primeiro `ADMIN` sem mexer no banco na mão. Criar um comando (`make seed-admin`) ou uma
   migration de dados.
3. **`response_model` no register** e uso do `Token` no login.
4. **Rodar os testes no CI** (GitHub Actions) a cada push.
5. **Front-end** consumindo o que já existe: lista de músicas, tela da letra (fonte grande, modo
   escuro, sem rolagem automática) e a playlist do culto.

> A tela da letra é o que a equipe vai usar no domingo. Vale caprichar nela antes de qualquer
> funcionalidade nova.

---

## 3. Fase 2 — API pronta para o front (concluída)

Um bloco pequeno de API feito **antes** do front começar. São mudanças baratas agora e caras depois,
porque mexem justamente no que toda tela usa. Uma semana.

### Cifras para os músicos, letra limpa para os membros

Uma coluna nova em `songs` guardando a letra com os acordes marcados entre colchetes, no formato
ChordPro:

```
[G]Antes de eu [D]falar, Tu já [Em]sabes
```

Dessa linha única saem as duas visões: tirando os colchetes, a letra limpa para os membros; jogando
os acordes para a linha de cima, a cifra para os músicos. O texto não é guardado duas vezes, então
não tem como as duas versões divergirem — que é exatamente o problema que o Centric existe para
resolver.

De brinde vem a **transposição de tom**: como o sistema sabe que `G` é um acorde e não a letra G de
uma palavra, dá para subir ou descer meio tom e recalcular tudo. O campo `tone` que já existe vira o
tom original.

Quem vê o quê é um parâmetro na requisição (`?view=chords` ou `?view=lyrics`), não uma permissão. Um
membro querer ver a cifra não é problema de segurança.

### Os três ajustes que o front vai pedir de qualquer jeito

- **Token durando mais** (8 horas, ou refresh token). Hoje são 30 minutos.
- **`GET /auth/me`**, devolvendo id, nome, e-mail e papel.
- **Busca vazia devolvendo `total: 0`** em vez de 404.

### Por que antes do front

A tela da letra é a mais usada do sistema, e essas quatro coisas mudam justamente ela e o cliente de
API. Feitas agora, o front constrói a tela uma vez. Feitas depois, ele reconstrói.

---

## 4. Fase 3 — RBAC de verdade (concluída)

Hoje o controle é `role == "ADMIN"` numa string. Funciona para duas pessoas, quebra quando a
igreja tiver líder de louvor, líder de pregação, equipe de mídia e recepção.

### Modelo sugerido

Três papéis globais + papéis por ministério:

**Papéis globais (`users.role`)**

| Papel | Pode |
|---|---|
| `ADMIN` | tudo: usuários, ministérios, eventos, músicas, escalas |
| `LEADER` | criar eventos, escalar pessoas e montar playlists **do ministério que lidera** |
| `MEMBER` | consultar músicas, letras, playlists e a própria escala; confirmar presença |

**Papel por ministério (`ministry_members.role`)**

```
Ministry            id, name ("Louvor", "Pregação", "Mídia"), description
MinistryMember      id, ministry_id, user_id, role ("LEADER" | "MEMBER"), instrument
```

Assim o líder de louvor escala músicos e monta playlist, mas não mexe na escala de pregadores.

### Como implementar

Trocar a dependência única por uma fábrica de dependências:

```python
# app/core/dependencies.py

def require_roles(*roles: str):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Permissão insuficiente")
        return current_user
    return checker


def require_ministry_leader(ministry_id: int, ...):
    """ADMIN passa sempre; LEADER só no ministério em que é líder."""
```

Uso: `admin: User = Depends(require_roles("ADMIN", "LEADER"))`.

Passos: enum de papéis → tabelas `ministries` e `ministry_members` → migration (todo `USER` vira
`MEMBER`) → trocar `require_admin` pelas novas dependências → testes de permissão.

---

## 5. Fase 4 — Escalas (músicos e pregadores) (concluída)

Aqui o Centric deixa de ser um repositório de letras e vira a ferramenta de organização do culto.

### Novas entidades

```
Event          id, title, date, time, type ("CULTO_DOMINGO", "ENSAIO", "EVENTO"),
               status ("RASCUNHO" | "PUBLICADO"), created_by

Assignment     id, event_id, user_id, ministry_id,
               function ("Vocal", "Guitarra", "Bateria", "Pregador", "Projeção"),
               status ("CONVIDADO" | "CONFIRMADO" | "RECUSADO"),
               responded_at, notes

Preaching      id, event_id, preacher_id, theme, bible_reference, notes

Availability   id, user_id, date, available (bool), reason
               (opcional — entra só se a equipe pedir)
```

### Relação com o que já existe

A `Playlist` passa a pertencer a um `Event`: adicionar `playlist.event_id` (nullable no começo,
para não quebrar as playlists já criadas). Um culto passa a ter, no mesmo lugar: a data, quem
está escalado, quem prega e o repertório.

### Endpoints

```
POST   /events/                            (admin, leader)
GET    /events/                            filtros: de/até, tipo, status
GET    /events/{id}                        culto completo: escala + pregação + playlist
PUT    /events/{id}
DELETE /events/{id}

POST   /events/{id}/assignments            escalar alguém
PATCH  /assignments/{id}                   trocar função/pessoa
DELETE /assignments/{id}
POST   /assignments/{id}/respond           confirmar ou recusar (o próprio escalado)

GET    /me/assignments                     "onde eu estou escalado"
GET    /events/{id}/preaching
```

### Regras que valem a pena ter

- Avisar (não bloquear) quando a mesma pessoa é escalada em dois ministérios no mesmo culto.
- Avisar quando uma música foi usada nas últimas *N* semanas — evita repetir demais.
- Histórico: "quando cantamos Ousado Amor pela última vez?" é a pergunta que mais aparece.

---

## 6. Fase 5 — IA (Gemini) montando o escopo da programação (concluída)

### Fluxo

1. O líder escreve em texto livre: *"Culto de domingo à noite, tema entrega, ceia no final,
   1h30, quero começar celebrativo e fechar em adoração."*
2. O front chama `POST /events/{id}/program/suggest` com esse briefing.
3. **O backend monta o prompt** (nunca o front) com:
   - o briefing;
   - o catálogo de músicas em formato compacto (`id`, título, tom, categoria);
   - quem está escalado e em qual função;
   - o histórico das últimas 4 semanas, para não repetir;
   - a duração alvo.
4. O Gemini responde em **JSON estruturado** (`response_schema`), com blocos de programação e
   `song_id` vindos **do catálogo**.
5. O backend **valida** (todo `song_id` existe? a soma dos tempos bate?) e devolve como
   **rascunho**.
6. O líder revisa e edita na tela. Só então `POST /events/{id}/program/apply` grava a playlist.

> Regra de ouro: a IA sugere, o humano aprova. Nada de a IA escrever direto na playlist do culto.

### Formato de resposta sugerido

```json
{
  "resumo": "Abertura celebrativa, transição para entrega, ceia em clima de adoração.",
  "blocos": [
    {"ordem": 1, "tipo": "MUSICA",  "song_id": 12, "duracao_min": 5, "motivo": "abertura celebrativa"},
    {"ordem": 2, "tipo": "MUSICA",  "song_id": 7,  "duracao_min": 6, "motivo": "mesmo tom, transição suave"},
    {"ordem": 3, "tipo": "MOMENTO", "titulo": "Boas-vindas e avisos", "duracao_min": 5},
    {"ordem": 4, "tipo": "PREGACAO","titulo": "Entrega", "duracao_min": 35},
    {"ordem": 5, "tipo": "MOMENTO", "titulo": "Ceia", "duracao_min": 15}
  ],
  "alertas": ["A música X foi usada nas últimas 2 semanas"]
}
```

### Implementação

- `pip install google-genai`
- `GEMINI_API_KEY` no `.env` e em `Settings` — **a chave nunca vai para o front**.
- Isolar em `app/services/ai_service.py`, atrás de uma interface simples
  (`suggest_program(event, briefing) -> ProgramSuggestion`), para poder trocar de modelo depois.
- Guardar cada sugestão numa tabela `program_suggestions` (briefing, resposta, quem pediu). Serve
  de histórico e evita pagar duas vezes pela mesma pergunta.
- Tratar erro e timeout: se a IA falhar, a tela continua funcionando no modo manual.

### Custo

Um culto gasta mais ou menos 3.000 tokens de entrada e 1.500 de saída. Com o **Gemini Flash-Lite**
(US$ 0,30 por 1M de entrada e US$ 2,50 por 1M de saída), isso dá cerca de **US$ 0,004 por
sugestão** — 8 cultos por mês custam centavos. O **free tier** do Gemini provavelmente cobre o uso
da igreja inteira sem custo nenhum; a conta paga entra só se vocês quiserem limites maiores e a
garantia de que o conteúdo não é usado para treinar os modelos do Google.

---

## 7. Fase 6 — Administração pela tela

O RBAC da fase 3 funciona, mas hoje é decorativo: `/ministries` tem **duas rotas, as duas de
leitura**. Não existe jeito de criar um ministério, pôr gente dentro, dizer quem lidera ou promover
alguém. Para a North sair do zero, alguém precisa rodar SQL na mão — os próprios testes criam
ministério com `Ministry(name="Louvor")` direto no banco, o que funciona no teste e não na vida.

**A meta da fase:** depois dela, o único comando fora da tela é o `make seed-admin`, que cria o
primeiro admin e roda uma vez na vida do sistema. Todo o resto é pela aplicação.

### Entrada por convite, não por fila de aprovação

Hoje qualquer pessoa com o endereço do site se cadastra e vê o repertório e a escala inteira. O
cadastro aberto acaba: quem entra, entra por um convite criado por um admin ou por um líder.

O convite carrega o papel e o ministério **dentro dele**. A pessoa abre o link, escolhe a própria
senha e já entra funcionando — sem ninguém aprovando nada depois.

A fila de aprovação foi descartada de propósito. Ela existe para quando você não sabe quem está
batendo na porta, que é o caso de um fórum público e não o de uma igreja. E resolve só metade:
depois de aprovar o cadastro, ainda falta promover a pessoa e ligá-la ao ministério.

Sem serviço de e-mail: o admin copia o link e manda no WhatsApp.

### Promover é um ato só

Para alguém ser líder, duas coisas precisam ser verdade em dois lugares: `users.role = LEADER` e um
`MinistryMember` com `role = LEADER`. Se a tela permitir escrever uma sem a outra, nasce o
**meio-líder**: quem tem o papel global e nenhum ministério não consegue nada, e quem lidera o
ministério mas ficou como `MEMBER` também não.

A regra: **uma rota só escreve os dois lados, na mesma transação**. E o contrário também — quem
deixa de liderar o último ministério volta a ser `MEMBER` sozinho.

Dívida anotada: o certo seria apagar `LEADER` do papel global e derivar "é líder" da participação no
ministério, uma fonte de verdade só. Reescreve a camada de permissão inteira, então fica para depois.

### Quem pode convidar quem

| Quem convida | Pode criar convite para |
|---|---|
| `ADMIN` | qualquer papel, qualquer ministério |
| `LEADER` | `MEMBER`, e só para o ministério que ele lidera |

Promover a líder continua sendo decisão de admin.

### Senha e acesso

Faltam três coisas que, sem elas, a promessa da fase não se cumpre — em todas, a saída hoje é SQL
no banco:

- **Trocar a própria senha.** Não existe rota.
- **Senha esquecida.** Sem serviço de e-mail, o caminho é o mesmo do convite: o admin ou o líder
  gera um link de redefinição e manda no WhatsApp. Mesma mecânica (token com validade e uso único),
  então cabe na mesma tabela, com um campo dizendo se o token é convite ou redefinição.
  O admin gera para qualquer pessoa; o líder, só para `MEMBER` do ministério que lidera. O link dá
  acesso à conta, então ninguém pode gerá-lo para uma conta com mais poder que a sua.
- **Tamanho mínimo de senha.** Hoje `password` é uma string sem validação nenhuma.

Junto disso vai o **rate limit no login**, que já estava na seção de segurança e nunca foi feito.
Antes de o endereço ficar público, login sem limite é convite para força bruta.

### O que esta fase não muda

- **Cadastro de música continua só do admin** — decisão da equipe.
- **Membro continua vendo tudo**: escala, repertório e letras. O que protege é a porta de entrada.
- **Apagar ministério fica de fora**: ministério que já apareceu em escala não some sem levar
  histórico junto. Renomear resolve o caso real.

---

## 8. Depois — n8n + WhatsApp (fora das fases)

> **Fora das fases, de propósito.** É a única parte do projeto com custo recorrente e a única que
> depende de gente de fora da equipe técnica: número da igreja, template aprovado pela Meta, telefone
> de cada pessoa. Só faz sentido quando o sistema já estiver rodando de verdade e a escala existir. O
> desenho e os preços ficam registrados aqui para o dia em que essa hora chegar.

### Arquitetura

O n8n não fala com o banco direto. Ele conversa com a API, nos dois sentidos:

```
                    ┌────────────────────────────────────────────┐
                    │                                            │
  Centric API ──────┤ 1. webhook: "escala publicada"             │
                    │    POST https://n8n.../webhook/escala      │
                    │                                            │
                    │ 2. cron n8n (todo dia 08h):                │
                    │    GET /events?de=hoje&ate=+3dias          │──→ WhatsApp
                    │                                            │
  Centric API ◄─────┤ 3. resposta do escalado:                   │
                    │    POST /assignments/{id}/respond          │
                    └────────────────────────────────────────────┘
```

Para o passo 3, a API precisa de um **token de confirmação** por escala (um link curto assinado),
para que a pessoa confirme sem precisar fazer login.

### O que automatizar (nessa ordem)

1. **D-3: lembrete de escala** — "Você está escalado no domingo (26/05) no vocal. Confirma?"
2. **D-1: lembrete com a playlist** — link da playlist do culto com as letras e tons.
3. **Na hora da publicação** — aviso de que a escala do mês saiu.
4. **Mudança de última hora** — alguém recusou, avisar o líder do ministério.

### Custos — as três opções

| Opção | Custo mensal | Risco | Observação |
|---|---|---|---|
| **WhatsApp Cloud API (oficial, Meta)** | ~R$ 20–25 | Nenhum | Mensagem *utility* custa ~R$ 0,04–0,05. Precisa de template aprovado |
| **Evolution API / Baileys (não oficial)** | R$ 0 de licença + VPS | **Alto** | Banimento permanente do número, sem recurso |
| **Telegram Bot** | R$ 0 | Nenhum | Grátis e sem template, mas a igreja precisa estar no Telegram |

**Conta realista do WhatsApp oficial:** 30 pessoas escaladas × 8 cultos × 2 mensagens =
480 mensagens/mês × R$ 0,05 ≈ **R$ 24/mês**. E como toda mensagem *dentro da janela de 24h*
aberta por uma resposta da pessoa é gratuita, na prática sai bem menos. Mensagens de *serviço*
(dentro da janela) são gratuitas desde novembro de 2024.

**n8n:**

| Modo | Custo |
|---|---|
| Self-hosted (Community Edition) | Grátis. VPS R$ 30–60/mês — ou na mesma máquina da API |
| n8n Cloud Starter | €20/mês (~R$ 115) — 2.500 execuções/mês |

**Total estimado do projeto rodando:** entre **R$ 25 e R$ 90 por mês**, dependendo de onde o n8n
e a API forem hospedados. Para uma igreja, o cenário mais barato (VPS única com API + n8n +
Postgres + WhatsApp Cloud API oficial) fica na casa de R$ 60–90/mês, com o WhatsApp custando
menos de R$ 25 disso.

### Recomendação

Usar a **Cloud API oficial da Meta**. A economia da Evolution API é de uns R$ 25/mês e o preço do
erro é perder o número da igreja de forma permanente. Se o orçamento for zero no começo, comece
com **Telegram** ou com um **e-mail de lembrete** e migre para o WhatsApp depois — a arquitetura
do n8n não muda, só o nó final.

---

## 9. Segurança e operação

- **LGPD**: telefone é dado pessoal. Coletar só de quem participa das escalas, com consentimento
  registrado, e permitir sair do envio.
- **Secrets** (`SECRET_KEY`, `GEMINI_API_KEY`, token do WhatsApp) nunca no repositório. O `.env`
  já está no `.gitignore` e nunca foi commitado (conferido: `git log -- .env` não retorna nada).
- **Backup do Postgres**: dump diário. A letra certa da música é o ativo do sistema.
- **Rate limit** no `/auth/login` — entra na fase 6.
- Token JWT: resolvido na fase 2, expira em 8 horas. Refresh token continua não existindo, e por
  enquanto não faz falta.

---

## 10. Ordem sugerida

| Fase | Entrega | Situação |
|---|---|---|
| 1 | CORS, primeiro admin, CI e testes em banco separado | Feita |
| 2 | Cifras, `/auth/me`, token mais longo, busca vazia | Feita |
| 3 | RBAC com ministérios | Feita |
| 4 | Eventos, escalas e pregadores | Feita |
| 5 | Sugestão de programação com o Gemini | Feita |
| 6 | Administração pela tela: convites, ministérios e papéis | 1 semana |

A fase 6 é a última do back-end, e destrava o resto: sem criar ministério e sem promover líder pela
tela, o RBAC das fases 3 e 4 só funciona com SQL na mão. O n8n e o WhatsApp continuam fora da conta.

Ela também muda o front antes de ele começar: a tela "Criar conta" vira "Criar conta pelo convite",
e entra uma tela de administração. Como o front ainda não existe, isso é de graça agora e seria
retrabalho depois.

No front, a checagem de papel deve ficar isolada numa função só (`podeEditar(usuario)`): os papéis
hoje são `ADMIN`, `LEADER` e `MEMBER`, e a regra de quem monta repertório é "qualquer líder", não
"o dono do evento".

---

## Fontes de preço

- [WhatsApp Business Cloud API — pricing oficial (Meta)](https://developers.facebook.com/docs/whatsapp/pricing)
- [WhatsApp Business API Pricing in Brazil 2026 (Message Central)](https://www.messagecentral.com/blog/whatsapp-business-api-pricing-brazil)
- [n8n — pricing oficial](https://n8n.io/pricing/)
- [Gemini API — pricing oficial (Google)](https://ai.google.dev/gemini-api/docs/pricing)
- [Evolution API: como funciona, custos e riscos (Cubo Suite)](https://blog.cubosuite.com.br/evolution-api-guia-completo/)
