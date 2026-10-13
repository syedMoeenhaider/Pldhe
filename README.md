# PLDHE — Punjab Livestock Digital Health Ecosystem

**Final Year Project (BSCS, University of Layyah)** — an AI-assisted veterinary triage,
rural location resolver, and autonomous telephony dispatch ecosystem for rural
Pakistan (pilot district: **Layyah**).

## What it does (in one paragraph)

A farmer in a village near Layyah **calls PLDHE live** (phone call or web
call) and speaks in **Saraiki / Punjabi / Urdu** about his animal's symptoms.
The Voice-AI intake assistant listens, triages mid-call, and on EMERGENCY
asks for consent live to dispatch the nearest vet. Every call's transcript is
analyzed — symptoms are mapped to likely livestock diseases (FMD, Lumpy Skin
Disease, Hemorrhagic Septicemia / Gal Ghotu…), risk is classified
(**EMERGENCY / HIGH / MEDIUM / LOW**), the village/Chak is extracted from the
conversation, and the case branches into one of four dispatch paths —
including an **autonomous Voice-AI call to the Punjab Livestock Helpline**
that files the complaint and brings back the official tracking number.

## Architecture

```
 Farmer ── LIVE CALL (phone / web, Saraiki·Punjabi·Urdu) ──► Vapi.ai
        intake assistant ── transcript ──►┌──────────────┐
                                         │   FastAPI    │
                                         │   Backend    │◄──┐
                                         │ Triage+NLP   │   │ mid-call:
                                         │ Dispatch     │   │ triage_symptoms
                                         └──────┬───────┘   │ tool
                                                │◄──────────┘
                                                ▼
                                    ┌───────────────────┐
                                    │  PostgreSQL       │
                                    │  + PostGIS        │
                                    └────────┬──────────┘
                                             │ webhooks
        ┌─────────────────┴──────────────────┐
        ▼                                    ▼
 ┌──────────────┐                    ┌──────────────┐
 │  n8n (Docker)│ ── POST /call ──►  │  Vapi.ai     │
 │  workflows   │                    │  Voice Agent │
 └──────────────┘                    └──────┬───────┘
        ▲                                    │ outbound call
        │            ┌───────────────┐        ▼
        └────────────│ Punjab Livestock Helpline │
                     │  → Complaint Tracking No │
                     └───────────────┘
```
(Web-app audio upload + Leaflet dashboard remain as secondary channels —
see Next.js frontend roadmap.)

## Repository layout (walking skeleton)

```
fyp-pldhe/
├── docker-compose.yml          # Postgres+PostGIS, backend, n8n — one command up
├── render.yaml                 # one-click Render deploy (backend)
├── DEPLOY.md                   # free live-deploy guide (Supabase + Render + Vercel)
├── frontend/                   # Next.js — "Live Baat Karein" web app (Vapi Web SDK)
│   ├── app/page.tsx            # glowing call button + live transcript + 6 phases
│   └── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   ├── test_triage.py          # triage logic demo (run: python test_triage.py)
│   └── app/
│       ├── main.py             # FastAPI app + all endpoints
│       ├── config.py           # settings via environment
│       ├── database.py         # engine, session, init_db
│       ├── models.py           # SQLAlchemy models (PostGIS-enabled)
│       ├── schemas.py          # Pydantic request/response schemas
│       ├── triage.py           # symptom → disease → risk engine (Module A)
│       ├── language.py         # Saraiki-first STT profiles + dialect normalization
│       ├── location.py         # rural location resolver (Module C)
│       ├── dispatch.py         # 4-path branching + Vapi/n8n triggers (Module B)
│       └── vision.py           # Phase 2 CV hook: breed + weight estimation
├── docs/
│   └── multilingual-stt.md     # Saraiki-first STT strategy + fine-tuning roadmap
└── n8n/
    ├── helpline-proxy-workflow.json  # importable n8n workflow
    ├── vapi-intake-assistant-prompt.md  # Saraiki-first farmer-facing assistant
    ├── vapi-assistant-prompt.md         # Urdu helpline proxy-call assistant
    └── blueprint.md                      # payload contracts + curl tests
```

## Quickstart

```bash
cd fyp-pldhe
cp backend/.env.example backend/.env   # fill in VAPI keys when ready
docker compose up --build
# API docs → http://localhost:8000/docs
# n8n        → http://localhost:5678
```

Triage demo without docker:

```bash
cd backend && python test_triage.py
```

## API (walking skeleton)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/intake` | Intake (live-call transcript / audio upload / text + GPS) → triage → dispatch plan |
| POST | `/api/v1/triage/live` | Mid-call triage tool for the Vapi intake assistant |
| POST | `/api/v1/webhooks/vapi-intake` | Vapi end-of-call transcript → case + triage + plan |
| POST | `/api/v1/cases/{id}/dispatch` | Farmer consent → executes the chosen path |
| GET | `/api/v1/cases` | List cases (filters: risk, status, tehsil) |
| GET | `/api/v1/cases/{id}` | Case detail |
| GET | `/api/v1/vets/nearby?lat&lon&radius_km` | Nearest vets via PostGIS |
| GET | `/api/v1/dashboard/heatmap` | Cases aggregated for Leaflet heatmap |
| POST | `/api/v1/cases/{id}/helpline-proxy` | Trigger autonomous helpline call |
| POST | `/api/v1/webhooks/vapi` | Vapi call callbacks (tracking-number capture) |

## Roadmap to defense

- [x] Walking skeleton: schema, triage engine, dispatch branching, Vapi/n8n blueprint
- [x] Live-call-first intake (Vapi webhooks, mid-call triage tool, Saraiki intake prompt)
- [x] Frontend skeleton: Next.js "Live Baat Karein" page (Vapi Web SDK) — deploy free on Vercel
- [x] Phase 2 CV hook contract (`vision.py`), vet SMS with map pin, Phase 6 closing-the-loop
- [ ] Wire faster-whisper + real Vapi assistants; Saraiki fine-tuning corpus grows from consented calls
- [ ] Real Tehsil boundary shapefile loaded into PostGIS (replaces bbox fallback)
- [ ] Vapi assistant created + test proxy call to helpline
- [ ] Outbreak alert thresholds + SMS to vets
- [ ] Defense slide deck + demo script
