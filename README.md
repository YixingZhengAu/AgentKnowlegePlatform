# Clenergy Enterprise Knowledge Agent

A demo system for tiered enterprise knowledge governance with agent-routed Q&A. Three knowledge types are tiered by error tolerance: **exact Q&A pairs** (zero rewriting), **document knowledge** (RAG + mandatory citations), and **analytics Q&A** (semantic layer + Text2SQL).

- Requirements & architecture: [documents/PRD.md](documents/PRD.md)
- Stage plans: [S0](documents/S0-PLAN.md) (foundation) · [S1](documents/S1-PLAN.md) (exact Q&A, done)
- Single source of truth for the schema: [documents/DB-DESIGN.md](documents/DB-DESIGN.md)
- Single source of truth for frontend style: [documents/UI-STYLE.md](documents/UI-STYLE.md)

> The UI and all Q&A interactions are English-only (the platform targets Australian users). Internal design documents and code comments are written in Chinese.

## Requirements

| Dependency | Version |
| --- | --- |
| Python | 3.13 |
| uv | 0.8+ (uv is the only Python dependency manager; `pip install` is not allowed) |
| Node | 22+ (tested on 24) |
| Docker | 28+ (runs Postgres 16 + pgvector) |

## From zero to running: one command

On a fresh clone, this is the only thing you need to run. `bootstrap.sh` checks the toolchain,
generates `.env` (auto-generating `SECRET_KEY` and prompting for your `OPENAI_API_KEY`),
installs backend and frontend dependencies, starts Postgres, creates the tables, seeds demo data,
and finally runs the offline tests, lint, and an LLM smoke test:

```bash
./bootstrap.sh            # or: make bootstrap
make dev                  # frontend :5173, backend :8000 (Swagger at /docs)
```

It is idempotent and safe to re-run (an existing `.env` is never overwritten). Common flags:

| Flag | Effect |
| --- | --- |
| `--with-mineru` | Also set up the PDF parsing container (builds the image and downloads ~1GB of weights, ~10 min; required for PDF upload through the S1 pipeline) |
| `--skip-smoke` | Skip the smoke test that really calls the LLM/embedding APIs (saves money, but no longer verifies your key) |
| `--reset` | Drop and recreate the database first (loses demo data; only removes the Postgres volume, MinerU weights are untouched) |
| `-y` | Non-interactive (CI / unattended) |
| `--help` | Full usage |

**Two things it cannot install** (system-level; the script only checks and tells you how): Docker 28+ and Node 22+.
You do not need to install Python 3.13 yourself — `uv` fetches it.

The manual step-by-step equivalent: `make install` → `make db` → `make migrate` → `make seed` → `make smoke`.

Once it is up, open http://localhost:5173:

- **Chat** — send a message and watch the reply stream in; the trace panel on the right lists
  latency / tokens / cost per stage. Click any past message to expand the prompt that was actually sent.
  While streaming, Send turns into Stop (a real interrupt — the message is persisted as `interrupted`).
  When an adopted exact Q&A is hit, the bubble carries a **Verified Answer** badge plus citations
  (matched phrasing, similarity, page number), and the trace contains **only `retrieve_exact_qa`,
  no `generate`** — the answer is verbatim from the knowledge base, zero rewriting.
  Badges and citations survive a page refresh (the history endpoint returns them), and
  **knowledge that was never adopted carries no badge** — ask about a fact from the same document
  that was not adopted and you just get "I don't know".
- **Exact Q&A ingestion** (`/ingest/exact-qa`) — the full S1 pipeline: upload a PDF → wait for parsing
  (the list updates itself) → **proofreading page** (original PDF on the left, parsed markdown on the
  right, editable with preview) → "Confirm & extract Q&A" → review each candidate with
  **Accept & publish** (adopting publishes it, immediately retrievable) / Reject (a reason is required) /
  multi-select for **bulk accept** → **Published Q&A** at the bottom of the page shows the number of
  indexed phrasings per item and an unpublish toggle. The trash icon on a document row deletes a
  wrongly uploaded document (two-step confirmation; refused while it still has published Q&A —
  unpublish those first).
- **Knowledge Bases / Agents** — the 3 seeded KBs and the default agent (with its system prompt and KB bindings)
- **Ingestion** — submit a fake job (`demo_sleep`) and watch the progress bar walk through four steps;
  `Inject a failure at` makes a chosen step fail so you can recover with "retry from failed step"
- **Review** (click Review at the end of a finished demo job row; S1 candidate review uses the same
  console) — 20 pending items: sorted by confidence, filterable by status, editable content,
  bulk approve/reject, keyboard flow (`j/k` to move, `a` approve, `x` reject, space to select),
  then **Publish** in the top right (writes a `publish_records` audit entry; the console becomes read-only after publishing)
- `/styleguide` is the hidden UI acceptance reference page

You can also try the Q&A straight from curl:

```bash
AGENT=$(curl -s localhost:8000/api/agents | python3 -c 'import sys,json;print(json.load(sys.stdin)["items"][0]["id"])')
curl -N -X POST localhost:8000/api/agents/$AGENT/chat \
  -H 'Content-Type: application/json' -d '{"question":"What can you help me with?"}'
# Take message_id from the done event to inspect the trace (stages / latency / tokens / cost)
curl localhost:8000/api/traces/<message_id>
```

To view the UI without a backend: `make demo` builds the single-file preview
`web/dist-demo/preview.html` (fixture data, zero external requests; the chat really streams and the
review console really changes state).

## Common commands

```
make help       list every command
make bootstrap  one-shot environment setup (same as ./bootstrap.sh — run this on a new machine)
make db         start the database (waits until healthy)
make mineru     start the MinerU PDF parsing container (18001, needed for S1 uploads)
make psql       open psql on the system database
make migrate    run Alembic migrations
make seed       load the minimal demo data
make db-reset   drop, recreate, migrate and seed (loses data; routine while the schema is changing)
make api        backend only
make web        frontend only
make dev        backend + frontend
make smoke      smoke test: real LLM and embedding calls (verifies key / network / proxy)
make smoke-s1   smoke test: the full S1 exact Q&A pipeline (needs make api + make mineru; costs real money)
make smoke-sse  smoke test: the frontend SSE client against the real backend (start the backend first)
make test       offline tests (no network, no DB)
make lint       backend ruff + frontend eslint + TS compile
make demo       build the single-file static preview (fixture data, no backend needed)
make types      openapi.json -> web/src/api/types.gen.ts (the frontend must never hand-write API types)
```

## Layout

```
bootstrap.sh     environment setup: toolchain check + .env + deps + db + migrate + seed + self-check
docker/          container config: Postgres init scripts + the MinerU parsing image
server/          FastAPI backend (managed by uv), see server/claude.md
web/             React + Vite frontend, see web/claude.md
documents/       PRD / stage plans / database design / UI guidelines
```

## The two databases

| Database | Purpose | Account |
| --- | --- | --- |
| `agent_system` | every business table of this system (knowledge, ingestion, sessions, traces, evaluation) | `postgres` |
| `clenergy_biz` | the demo business database, target of analytics Q&A | `biz_reader` (read-only, no CREATE, cannot connect to the system database) |
