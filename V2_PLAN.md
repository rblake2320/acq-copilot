# ACQ-COPILOT V2 — Full Implementation Plan

> **Reference document**: Read this file on GitHub to maintain context across auto-compacts.
> **Branch**: `v2` | **Repo**: https://github.com/rblake2320/acq-copilot
> **Status**: Implementation in progress — see Phase checklist below

---

## Codebase Map (existing, don't break)

```
/d/acq-copilot-v2/
├── apps/
│   ├── api/                          ← FastAPI backend (Python)
│   │   ├── app/
│   │   │   ├── main.py               ← FastAPI app entry
│   │   │   ├── config.py             ← Settings / env vars
│   │   │   ├── dependencies.py       ← DB, cache injection
│   │   │   ├── models/database.py    ← SQLAlchemy models
│   │   │   ├── orchestration/        ← DEAD CODE — wire this up in Phase 1
│   │   │   │   ├── router.py         ← IntentRouter (11 categories)
│   │   │   │   ├── planner.py        ← ExecutionPlanner (dependency-aware)
│   │   │   │   ├── executor.py       ← ExecutionEngine (parallel)
│   │   │   │   ├── answer_synthesizer.py ← confidence scoring
│   │   │   │   ├── citations.py      ← CitationAggregator
│   │   │   │   ├── guards.py         ← PII, grounding, disclaimer (BUG: line 95 uses self in staticmethod)
│   │   │   │   ├── providers.py      ← Multi-LLM (Anthropic, OpenAI, Azure)
│   │   │   │   └── __init__.py
│   │   │   ├── routers/
│   │   │   │   ├── chat.py           ← BYPASSES orchestration — fix in Phase 1
│   │   │   │   ├── igce.py           ← IGCE estimate + Excel export
│   │   │   │   ├── regulatory.py     ← Fed Register + eCFR + Regulations.gov
│   │   │   │   ├── market_research.py← USASpending search
│   │   │   │   ├── admin.py          ← Health, audit, tool status
│   │   │   │   └── tools.py          ← List tools, run tool, health
│   │   │   ├── services/
│   │   │   │   ├── audit.py          ← Audit trail logging
│   │   │   │   └── cache.py          ← Redis caching layer
│   │   │   ├── tools/
│   │   │   │   ├── base.py           ← AcquisitionTool base class
│   │   │   │   ├── registry.py       ← ToolRegistry (8 tools registered)
│   │   │   │   ├── bls_oews.py       ← BLS Occupational Employment & Wage Stats
│   │   │   │   ├── ecfr.py           ← eCFR API search
│   │   │   │   ├── federal_register.py ← Federal Register API search
│   │   │   │   ├── gsa_calc.py       ← GSA CALC+ labor rates
│   │   │   │   ├── gsa_perdiem.py    ← GSA per diem rates
│   │   │   │   ├── igce_builder.py   ← IGCE calculation engine
│   │   │   │   ├── regulations_gov.py← Regulations.gov API search
│   │   │   │   └── usaspending.py    ← USASpending.gov API
│   │   │   └── schemas/common.py     ← Pydantic request/response schemas
│   │   ├── alembic/                  ← DB migrations
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── web/                          ← Next.js 15 frontend (TypeScript)
│       └── src/
│           ├── app/                  ← App Router pages
│           │   ├── page.tsx          ← Home dashboard
│           │   ├── chat/page.tsx     ← Chat analysis
│           │   ├── igce/page.tsx     ← IGCE builder (5-step wizard)
│           │   ├── regulatory/page.tsx
│           │   ├── market-research/page.tsx
│           │   └── admin/page.tsx
│           ├── components/
│           │   ├── chat/
│           │   │   ├── ChatInterface.tsx
│           │   │   ├── MessageBubble.tsx
│           │   │   ├── ToolTracePanel.tsx  ← Built but needs real data
│           │   │   └── CitationsList.tsx   ← Built but needs real data
│           │   ├── igce/IGCEForm.tsx + IGCEResults.tsx
│           │   ├── common/Sidebar.tsx
│           │   └── ui/button, card, badge, input, tabs
│           ├── lib/api.ts + store.ts + utils.ts
│           └── types/index.ts
├── docker-compose.yml
├── V2_PLAN.md                        ← THIS FILE
└── README.md
```

---

## Gap Analysis Summary

### What acq-copilot already does BETTER than acquisition.gov
| Feature | Acq-Copilot | Acquisition.gov |
|---------|-------------|-----------------|
| AI chat with acquisition expertise | Yes (Claude Opus) | No AI at all |
| IGCE builder with live BLS/GSA data | Yes (BLS OEWS + GSA per diem + Excel export) | No IGCE tools |
| USASpending market research | Yes (real API) | No |
| Multi-source regulatory search | Yes (Fed Register + eCFR + Regulations.gov parallel) | Keyword only |
| Sensitivity analysis | Yes (+/-10%) | None |

### Critical Gaps vs acquisition.gov
| Gap | Priority |
|-----|----------|
| Full FAR text (53 parts) with navigation | **P0 — Phase 2** |
| DFARS, GSAM/GSAR, 28+ agency supplements | **P0 — Phase 2** |
| Smart Matrix — unified clause finder | **P1 — Phase 2** |
| FAR Definitions Tool | **P1 — Phase 2** |
| Threshold Tracker (MPT/SAT/TINA) | **P2 — Phase 5** |
| Acquisition Gateway Solution Finder | **P1 — Phase 3** |
| Forecast of Contracting Opportunities | **P1 — Phase 3** |

### White Space (nobody in market does this)
1. **Unified lifecycle AI** — market research through post-award in one tool
2. **Cross-system AI aggregation** — SAM + FPDS + USASpending + CALC+ + BLS unified
3. **AI-powered IGCE from historical award data**
4. **Semantic FAR search** (embeddings, not keywords)
5. **Solicitation compliance checking** — FAR validation tool
6. **Price reasonableness AI** — CALC+ + FPDS + BLS combined
7. **Self-hosted on-prem** — agencies can't send data to cloud (GovWin, BGOV)

---

## Architecture (V2)

```
Next.js 15 frontend
    |
FastAPI backend
    |
    +-> Orchestration (DEAD CODE → wire up in Phase 1)
    |      IntentRouter → ExecutionPlanner → ExecutionEngine
    |      AnswerSynthesizer ← guards ← citations
    |
    +-> Tool Registry (8 existing + 12 new tools)
    |
    +-> RAG Engine (NEW — Phase 2)
    |      FAR/DFARS DITA XML from GSA/GSA-Acquisition-FAR GitHub
    |      pgvector + nomic-embed-text via Ollama (already running)
    |      HNSW index, semantic search endpoint
    |
    +-> Data Pipeline (NEW — Phase 3+)
    |      SAM.gov opportunity feed, FPDS sync, threshold updates
    |
    +-> PostgreSQL + pgvector | Redis
```

---

## Implementation Phases & Status

### ✅ Phase 0: Foundation
- [x] Clone repo, create `v2` branch
- [x] Commit full plan to GitHub (this file)
- [ ] Extract and verify all existing code compiles
- [ ] Set up local dev environment

### ✅ Phase 1: Wire the Brain (COMPLETE — commit 5771b54)
**Goal**: Route `POST /chat/send` through orchestration pipeline instead of direct Anthropic call

**Files to modify:**
- `apps/api/app/routers/chat.py` — replace direct Anthropic call with orchestration pipeline
- `apps/api/app/orchestration/guards.py` — fix staticmethod bug at line ~95
- `apps/api/app/orchestration/executor.py` — bridge to use `tools/registry.py` (currently duplicates registry)
- `apps/api/app/orchestration/__init__.py` — export pipeline entry point

**New files:**
- `apps/api/app/orchestration/pipeline.py` — thin wrapper: `run_pipeline(query, conversation_id) → ChatResponse`

**Frontend:**
- `apps/web/src/components/chat/ToolTracePanel.tsx` — connect to real tool_runs from response
- `apps/web/src/components/chat/CitationsList.tsx` — connect to real citations from response
- Add SSE streaming support for real-time tool execution feedback

**Success test**: Ask "What are the BLS rates for Software Developers in DC?" — should show tool trace with `bls.lookup` execution and citations

---

### ✅ Phase 2: FAR RAG Engine (COMPLETE — commit 665d712)
**Goal**: Semantic search over full FAR/DFARS — beats acquisition.gov keyword search

**Data source**: `https://github.com/GSA/GSA-Acquisition-FAR` (public DITA XML, 53 parts)

**New files:**
- `apps/api/app/tools/far_rag.py` — `far.semantic_search` tool
- `apps/api/app/routers/rag.py` — `POST /api/rag/search`, `GET /api/rag/far/{part}/{section}`
- `apps/api/app/services/far_ingest.py` — parse DITA XML → chunks → pgvector embeddings
- `apps/api/scripts/ingest_far.py` — one-time ingest script
- `apps/web/src/app/far-search/page.tsx` — new frontend page
- `apps/web/src/components/far/FARViewer.tsx` — section viewer with cross-references

**DB migration:**
```sql
CREATE TABLE far_sections (
    id SERIAL PRIMARY KEY,
    part INT, section VARCHAR(20), title TEXT, content TEXT,
    source VARCHAR(20),  -- 'FAR', 'DFARS', 'GSAM'
    effective_date DATE,
    embedding vector(768)  -- nomic-embed-text
);
CREATE INDEX ON far_sections USING hnsw (embedding vector_cosine_ops);
```

**Success test**: Ask "What are the rules for commercial item acquisitions under $250K?" → exact FAR sections with part/section links

---

### ✅ Phase 3: SAM.gov Opportunity Intelligence (COMPLETE — commit 3234824)
**Goal**: Real contract opportunity search + semantic matching

**API**: `https://api.sam.gov/opportunities/v2/search` (free, key from api.data.gov)

**New files:**
- `apps/api/app/tools/sam_opportunities.py` — `sam.search_opportunities` + `sam.entity_lookup`
- `apps/api/app/routers/opportunities.py` — `GET /api/opportunities/search`
- `apps/web/src/app/opportunities/page.tsx` — opportunity cards, filters, saved alerts

**Success test**: "Find IT opportunities in Virginia under $10M" → real SAM.gov results

---

### ✅ Phase 4: Compliance Checker (COMPLETE — commit 8f669e6)
**Goal**: Upload solicitation PDF → FAR compliance report (nobody else does this)

**New files:**
- `apps/api/app/tools/document_parse.py` — pdfplumber/pymupdf clause extraction
- `apps/api/app/tools/compliance_checker.py` — `compliance.check_solicitation`
- `apps/api/app/routers/compliance.py` — `POST /api/compliance/check`
- `apps/web/src/app/compliance/page.tsx` — drag-drop upload, findings display

---

### ✅ Phase 5: Acquisition Planning Assistant (COMPLETE — commit cb7b5eb)
**Goal**: "I need to buy X" → complete acquisition strategy

**New files:**
- `apps/api/app/tools/vehicle_recommender.py` — GWAC/IDIQ/BPA/Schedule recommendation
- `apps/api/app/tools/milestone_generator.py` — acquisition timeline
- `apps/api/app/tools/threshold_checker.py` — MPT/SAT/TINA lookup
- `apps/api/app/routers/planning.py` — `POST /api/planning/strategy`
- `apps/web/src/app/planning/page.tsx` — guided wizard

---

### ✅ Phase 6: Price Reasonableness Engine (COMPLETE — commit cb7b5eb)
**Goal**: Cross-source price analysis (BLS + CALC+ + USASpending → confidence score)

**New files:**
- `apps/api/app/tools/price_reasonableness.py` — unified price analysis
- `apps/api/app/routers/pricing.py` — `POST /api/pricing/analyze`
- `apps/web/src/app/pricing/page.tsx` — price range chart

---

### 🔄 Phase 7: Auth + Production Hardening (NEXT)
- JWT authentication, role-based access
- Multi-tenancy (organization/team)
- Rate limiting per user tier
- On-prem / Ollama deployment option

---

## New Tools (12 additions to existing 8)

| Tool ID | Purpose | Data Source | Phase |
|---------|---------|-------------|-------|
| `far.semantic_search` | Semantic search over full FAR/DFARS | pgvector local | 2 |
| `sam.search_opportunities` | Contract opportunity search | api.sam.gov | 3 |
| `sam.entity_lookup` | Contractor entity details | api.sam.gov | 3 |
| `fpds.contract_detail` | Detailed contract data (180+ fields) | fpds.gov | 3 |
| `compliance.check_solicitation` | FAR compliance validation | FAR RAG + LLM | 4 |
| `price.reasonableness` | Cross-source price analysis | BLS + CALC+ + USASpending | 6 |
| `vehicle.recommend` | GWAC/IDIQ/BPA recommendation | Acquisition Gateway | 5 |
| `threshold.check` | MPT/SAT/TINA threshold lookup | Hardcoded + updates | 5 |
| `small_business.analytics` | Set-aside tracking + SB stats | USASpending + SAM | 5 |
| `document.parse` | PDF/DOCX clause extraction | pdfplumber/pymupdf | 4 |
| `milestone.generate` | Acquisition timeline generator | Rules engine | 5 |
| `report.generate` | Formatted market research reports | All sources | 5 |

---

## Key Bug: guards.py staticmethod uses `self`

```python
# apps/api/app/orchestration/guards.py ~line 95
# BUG: staticmethod cannot reference self
@staticmethod
def some_check(data):
    return self.something(data)  # ← NameError at runtime

# FIX:
@staticmethod
def some_check(data):
    return GuardRails.something(data)  # ← reference class directly
```

---

## Key Bug: executor.py duplicates ToolRegistry

```python
# apps/api/app/orchestration/executor.py
# Creates its own dict of tools instead of using tools/registry.py
# FIX: import and use registry.get_tool(tool_id) instead
```

---

## Local Dev Setup

```bash
# Backend
cd /d/acq-copilot-v2/apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd /d/acq-copilot-v2/apps/web
npm install && npm run dev   # → http://localhost:3000

# PostgreSQL (user-mode, already running)
# pg_ctl start -D D:\PostgreSQL\data

# Redis (needed for caching)
# docker run -d -p 6379:6379 redis:alpine

# Ollama (for embeddings)
# ollama serve   (already running with nomic-embed-text)
```

---

## GitHub Workflow

```bash
# After each phase
cd /d/acq-copilot-v2
git add -A
git commit -m "Phase N: description"
git push origin v2

# If auto-compact happens, resume with:
# gh repo view rblake2320/acq-copilot → read V2_PLAN.md on v2 branch
# git -C /d/acq-copilot-v2 log --oneline -10
```

---

## Competition Comparison

| Advantage | vs GovWin IQ ($50K/yr) | vs BGOV ($7.5K/yr) | vs GovDash |
|-----------|----------------------|---------------------|------------|
| NL queries that run tools in parallel | They're search-and-browse | Same | Similar AI but proposal-focused |
| IGCE from live BLS + GSA data | Has rates but no IGCE | Has pricing but no estimates | No IGCE |
| Semantic FAR search | No FAR search | Policy tracking only | No FAR |
| Compliance checking | Not offered | Not offered | Proposal compliance only |
| Cross-system (6+ APIs) | 1-2 sources | 1-2 sources | Proposal-focused |
| Self-hosted/on-prem | Cloud only | Cloud only | Cloud only, FedRAMP Moderate |
| Free / open source | $10-50K/yr | $7.5K/user/yr | Custom pricing |
