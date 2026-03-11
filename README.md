# Acquisition Copilot

Acquisition intelligence platform with live federal data, deterministic IGCE computation, and AI-powered synthesis — built to replace prompt-file skill collections with a proper tool-using architecture.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Next.js 15 Frontend (TypeScript + Tailwind + shadcn)   │
│  Chat │ IGCE Builder │ Regulatory │ Market Research      │
└──────────────────────┬──────────────────────────────────┘
                       │ /api/*
┌──────────────────────┴──────────────────────────────────┐
│  FastAPI Backend                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Orchestration│  │ Tool Registry│  │ IGCE Engine   │  │
│  │ Router       │  │ 8 Connectors │  │ Deterministic │  │
│  │ Planner      │  │ + Plugin API │  │ Math Only     │  │
│  │ Synthesizer  │  │              │  │               │  │
│  │ Guards       │  │              │  │               │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│  ┌──────────┐  ┌───────────┐  ┌─────────────────────┐  │
│  │ Postgres │  │   Redis   │  │ LLM Providers       │  │
│  │ Audit/DB │  │   Cache   │  │ Anthropic/OpenAI/Az │  │
│  └──────────┘  └───────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — add at least one LLM API key

# 2. Start everything
docker compose up -d

# 3. Run migrations
docker compose exec api alembic upgrade head

# Frontend: http://localhost:3000
# API:      http://localhost:8000
# API docs: http://localhost:8000/docs
```

## Tool Connectors

| Tool ID | Source | Auth Required |
|---------|--------|---------------|
| `usaspending.search_awards` | USASpending.gov | No |
| `federal_register.search_documents` | Federal Register | No |
| `ecfr.get_section` | eCFR.gov | No |
| `bls.oews.lookup_wages` | BLS OEWS | Optional |
| `gsa.perdiem.lookup_location` | GSA Per Diem | No |
| `gsa.calc.search_rates` | GSA CALC+ | No |
| `regulations.search_dockets` | Regulations.gov | Yes |
| `igce.build` | Internal Engine | N/A |

## IGCE Engine

Deterministic pipeline — LLM never touches the math:

1. Map labor categories → BLS SOC codes
2. Pull wages by metro/state/national scope
3. Apply burden multiplier (versioned default: 2.0)
4. Apply escalation by year (compound or simple)
5. Pull GSA per diem by location
6. Calculate travel totals
7. Cross-check against CALC+ ceiling rates
8. Generate sensitivity analysis (low/base/high)
9. LLM synthesizes narrative only

## Development

```bash
# Backend
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd apps/web
npm install
npm run dev
```

## Core Design Principle

**Every answer is reproducible.** Each response stores: user prompt, normalized intent, tools selected, raw request params, raw response snapshot, calculation formulas, model synthesis, timestamps, and logic version.
