# GrillKit Architecture

GrillKit is an AI-powered technical interview trainer. The stack is **FastAPI** (HTTP + WebSocket), **SQLAlchemy** (SQLite), **Jinja2** templates, and an **OpenAI-compatible** AI adapter. Business logic lives in `services/`; transport in `api/`; pure rules in `domain/`; persistence in `repositories/` behind `UnitOfWork`.

## Project Map

```
grillkit/
├── app/
│   ├── main.py                 # create_app(), router registration, lifespan → init_db()
│   ├── database.py             # SQLite engine, SessionLocal, init_db()
│   ├── models.py               # Interview, Answer ORM models
│   ├── questions.py            # YAML question loader (data/questions/)
│   ├── templating.py           # Shared Jinja2Templates + static_version()
│   ├── uow.py                  # UnitOfWork: uow.interviews, uow.answers, uow.session
│   ├── domain/
│   │   ├── exceptions.py       # InterviewNotFoundError, InterviewNotActiveError, ...
│   │   ├── interview_progress.py   # find_first_unanswered(), find_unanswered_for_question(), ...
│   │   ├── interview_lifecycle.py  # MAX_SCORE_PER_ROUND, compute_interview_score(), ...
│   │   ├── locales.py          # SUPPORTED_LOCALES, normalize_locale()
│   │   └── speech_models.py    # Whisper size → Hugging Face model metadata
│   ├── ai/
│   │   ├── base.py             # AIProvider protocol
│   │   ├── factory.py          # ProviderFactory.from_config()
│   │   └── openai_compatible.py
│   ├── api/
│   │   ├── deps.py             # FastAPI Depends() → service classes
│   │   ├── dashboard.py        # GET /
│   │   ├── setup.py            # GET/POST /setup, GET /setup/options
│   │   ├── setup_form.py       # setup.html template context
│   │   ├── config.py           # GET/POST /config (provider settings)
│   │   ├── speech.py           # GET/POST /speech/model/* (Whisper download)
│   │   ├── dictation.py        # WS /interview/{id}/dictation (PCM buffer → final transcript)
│   │   ├── dictation_protocol.py  # Dictation WS message type constants + dictation_message()
│   │   ├── interview.py        # GET /interview/{id}, WS /interview/{id}/ws
│   │   ├── ws_protocol.py      # InterviewEvent → JSON messages
│   │   └── interview_errors.py # domain errors → HTTP / WebSocket payloads
│   ├── repositories/
│   │   ├── base.py             # Repository[T], SqlAlchemyRepository[T]
│   │   ├── interview.py        # InterviewRepository
│   │   └── answer.py           # AnswerRepository
│   └── services/
│       ├── config.py           # ProviderConfig, ConfigService (data/config.json)
│       ├── whisper_storage.py  # Whisper model paths and on-disk validation
│       ├── whisper_model.py    # Whisper model download and install
│       ├── whisper_runtime.py  # In-process faster-whisper load and hot-reload
│       ├── speech_recognition.py  # Buffered PCM dictation session
│       ├── interview_creation.py
│       ├── interview_query.py
│       ├── interview_completion.py
│       ├── answer_processing.py
│       ├── interview_evaluator.py
│       ├── interview_evaluator_models.py
│       ├── interview_evaluator_prompts.py
│       ├── interview_events.py   # AnswerSavedEvent, EvaluatingEvent, ...
│       └── ai_context.py         # ai_provider_from_config() async context manager
├── templates/                  # Jinja2 HTML (dashboard, setup, config, interview, speech_model_*)
├── static/
│   ├── css/styles.css
│   └── js/                     # dictation.js, speech_model.js (interview voice UI)
├── data/
│   ├── config.json             # AI provider + interview locale (gitignored)
│   ├── whisper-models/<size>/  # faster-whisper snapshots (gitignored content)
│   ├── db/grillkit.db          # SQLite database (gitignored, created at runtime)
│   └── questions/              # YAML banks: {language}/{level}/{category}.yaml
├── docker-compose.yml          # Primary deployment (port 8000, ./data volume)
├── docker-entrypoint.sh        # PUID/PGID, ensures data/db writable
├── Dockerfile                  # Multi-stage uv build → uvicorn
└── tests/
```

## HTTP Routes

| Method | Path | Module | Purpose |
|--------|------|--------|---------|
| GET | `/` | `dashboard.py` | Interview history (last 20) |
| GET | `/setup` | `setup.py` | New interview form (redirects to `/config` if unset) |
| POST | `/setup` | `setup.py` | Create interview → redirect `/interview/{id}` |
| GET | `/setup/options` | `setup.py` | Cascaded JSON: languages → levels → categories |
| GET | `/config` | `config.py` | AI provider configuration form |
| POST | `/config` | `config.py` | Test connection (via form dependency), then save |
| POST | `/config/test` | `config.py` | Test connection without saving |
| DELETE | `/config` | `config.py` | Remove saved provider configuration |
| GET | `/speech/model/status` | `speech.py` | Whisper model install status (HTML or JSON) |
| POST | `/speech/model/download` | `speech.py` | Start Whisper download for `config.speech_model_size` |
| GET | `/speech/model/options` | `speech.py` | JSON size trade-off metadata |
| GET | `/interview/{interview_id}` | `interview.py` | Interview page (active or completed) |
| WS | `/interview/{interview_id}/ws` | `interview.py` | Real-time answers and completion |
| WS | `/interview/{interview_id}/dictation` | `dictation.py` | PCM dictation: `start` → `ready`, audio chunks, `stop` → `final` |
| — | `/static/*` | `main.py` | CSS, JS, and assets |

## Layer Responsibilities

| Layer | Responsibility |
|-------|----------------|
| `api/` | HTTP/WebSocket transport, form handling, template rendering |
| `api/deps.py` | Inject service **classes** via `Depends` (handlers call static methods) |
| `api/ws_protocol.py` | Map `InterviewEvent` dataclasses → interview WebSocket JSON |
| `api/dictation_protocol.py` | Dictation WebSocket message types (`start`, `stop`, `ready`, `final`, `error`) |
| `api/interview_errors.py` | Map `InterviewDomainError` → error payloads |
| `services/` | Use-case orchestration (static methods on service classes) |
| `domain/` | Progress navigation, scoring rules, exceptions, locales (no I/O) |
| `repositories/` | Persistence only (SQLAlchemy via `SqlAlchemyRepository`) |
| `uow.py` | Single transaction boundary; exposes `interviews` and `answers` repos |
| `ai/` | Provider adapters (`AIProvider` protocol) |
| `questions.py` | Read-only YAML question bank access |

Application services are **stateless classes with `@staticmethod`**. FastAPI dependencies in `deps.py` return the class (e.g. `InterviewQuery`), not instances.

## Module Dependency Graph

Dependencies flow **downward** (caller → callee). Plain-text diagram for editors that do not render Mermaid.

```
main.py ──► lifespan: init_db(), WhisperRuntime.bind_app(), load configured Whisper size
  └── api/  (dashboard, setup, config, speech, interview, dictation)
        ├── interview.py ──► ws_protocol.py, interview_errors.py, WhisperModelService (page status)
        ├── dictation.py ──► dictation_protocol.py, DictationSession, app.state.whisper_model
        ├── speech.py    ──► WhisperModelService (status/download)
        └── deps.py ──► services/

services/
  ├── interview_creation.py ──► domain/, questions.py, uow.py
  ├── interview_query.py      ──► domain/, uow.py
  ├── interview_completion.py ──► domain/, interview_evaluator.py, ai_context.py, uow.py
  ├── answer_processing.py    ──► domain/, interview_evaluator.py, ai_context.py, uow.py
  ├── interview_evaluator.py  ──► ai/ (via provider), interview_evaluator_models.py, prompts
  ├── config.py               ──► ai/factory.py, domain/speech_models.py, data/config.json
  ├── whisper_model.py        ──► whisper_storage.py, whisper_runtime.py, Hugging Face hub
  ├── whisper_runtime.py      ──► whisper_storage.py, faster-whisper (app.state mirror)
  ├── whisper_storage.py      ──► domain/speech_models.py, data/whisper-models/
  ├── speech_recognition.py   ──► domain/locales.py (DictationSession PCM → text)
  └── ai_context.py           ──► config.py, ai/

uow.py
  └── repositories/ (interview.py, answer.py, base.py)
        └── models.py

database.py ──► models.py (Base, engine)
```

On GitHub, the same graph is also available as Mermaid (rendered on github.com only):

<details>
<summary>Mermaid source (GitHub preview)</summary>

```mermaid
flowchart TB
  main --> api_layer
  main --> whisper_runtime
  subgraph api_layer [api]
    dashboard
    setup
    config_router[config]
    speech_router[speech]
    interview
    dictation
    ws_protocol
    dictation_protocol
    interview_errors
    deps
  end
  interview --> ws_protocol
  interview --> interview_errors
  dictation --> dictation_protocol
  dictation --> speech_recognition
  speech_router --> whisper_model
  api_layer --> deps
  deps --> svc_layer
  subgraph svc_layer [services]
    interview_creation
    interview_query
    interview_completion
    answer_processing
    interview_evaluator
    config_service[config]
    whisper_model
    speech_recognition
    ai_context
  end
  whisper_model --> whisper_runtime
  whisper_model --> whisper_storage
  whisper_runtime --> whisper_storage
  svc_layer --> domain
  svc_layer --> uow
  svc_layer --> questions_mod[questions]
  interview_creation --> questions_mod
  ai_context --> config_service
  ai_context --> ai_layer
  subgraph ai_layer [ai]
    factory
    openai_compatible
  end
  uow --> repos
  subgraph repos [repositories]
    interview_repo[interview]
    answer_repo[answer]
  end
  repos --> models
```

</details>

## Naming Convention

| Concept | Name in code |
|---------|----------------|
| Interview ORM model | `Interview` (table `interviews`) |
| Primary key column | `Interview.id` (UUID string) |
| Route / WS path param | `interview_id` (same value as `Interview.id`) |
| Answer FK | `Answer.interview_id` → `interviews.id` |
| Create flow | `InterviewCreationService.create_interview()` |
| Read flow | `InterviewQuery.get_interview()`, `list_dashboard_rows()` |
| Answer flow | `AnswerProcessingService.process_answer_submission()` |
| Complete flow | `InterviewCompletionService.complete_interview()` |
| UoW repositories | `uow.interviews`, `uow.answers` |
| SQLAlchemy session | `uow.session` |

## Key Models

### Interview (`interviews`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | UUID v4 primary key |
| `level` | `str` | `junior`, `middle`, `senior` |
| `language` | `str` | Question bank slug (`python`, `database`, …) |
| `locale` | `str` | AI feedback language (`en`, `ru`, …) |
| `category` | `str` | YAML topic slug |
| `question_count` | `int` | Number of questions in session |
| `question_ids` | `str` | JSON list of question IDs in display order |
| `status` | `str` | `active` or `completed` |
| `score` | `int \| None` | Total score when completed |
| `overall_feedback` | `str \| None` | JSON string from final AI evaluation |
| `started_at`, `completed_at` | `datetime` | Session timestamps |

### Answer (`answers`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | `int` | Auto-increment PK |
| `interview_id` | `str` | FK to `interviews.id` (CASCADE delete) |
| `question_id` | `str` | ID from YAML bank |
| `order` | `int` | 1-based display order within session |
| `round` | `int` | `0` = initial question; `1+` = AI follow-up |
| `question_text`, `question_code` | `str` | Snapshot at ask time |
| `answer_text` | `str \| None` | User answer (`None` until submitted) |
| `score`, `feedback` | | Set after AI evaluation (score 1–5) |

Rows are created up front at interview creation (one per question, `round=0`). Follow-up rounds add new `Answer` rows via `AnswerRepository`.

## Data Flow: Configure Provider

```
User → GET /config → ConfigService.get_config()
User → POST /config/test → test only (no save)
User → POST /config → ProviderConfig from form
  → ConfigService.test_connection() → AI provider ping
  → on success: ConfigService.save_config() → data/config.json
User → DELETE /config → ConfigService.delete_config()
```

Setup and interview flows require a saved config; otherwise `/setup` redirects to `/config`.

## Data Flow: Create Interview

```
User → POST /setup (language, topic, level, question_count)
  → locale from ConfigService.get_config() → Interview.locale snapshot
  → InterviewCreationService.create_interview()
       → load_category() from YAML
       → shuffle & pick question_count questions
       → UnitOfWork(auto_commit=True): persist Interview + Answer rows (round=0)
  → Redirect GET /interview/{id}
```

## Data Flow: WebSocket Answer

```
Client → WS {"type":"answer","question_id":"...","answer_text":"..."}
  → AnswerProcessingService.process_answer_submission(interview_id, ...)
       → UoW #1: validate active, save answer_text, load context
       → ai_provider_from_config() → InterviewEvaluatorService (no DB transaction)
       → UoW #2: save score/feedback; optional follow-up Answer row or advance
       → stream_answer_submission() yields saved/evaluating, then feedback after AI
  → event_to_message() per event → client (not batched after evaluation)

Client → WS {"type":"ping"}
  → InterviewQuery.get_interview() → {"type":"pong","status":"active"|"completed"|...}
```

**Server → client message types:** `saved`, `evaluating`, `feedback`, `interview_completed`, `error`, `pong`.

## Data Flow: Dictation WebSocket

Separate from answer/evaluation WS. Requires active interview and loaded Whisper model (`app.state.whisper_model`).

```
Client → WS connect /interview/{id}/dictation
  → InterviewQuery.get_interview() + require_active()
  → reject if model missing (download via /config → /speech/model/download)

Client → {"type":"start"}
  → DictationSession() → {"type":"ready"}

Client → binary PCM (16-bit LE mono, 16 kHz)
  → DictationSession.append_pcm()

Client → {"type":"stop"}
  → DictationSession.finalize(whisper_model, interview.locale)
  → {"type":"final","text":"..."} → connection closes
```

**Server → client message types:** `ready`, `final`, `error`.

## Data Flow: Speech Model Install

```
User → GET /config (speech_model_size, locale)
User → POST /speech/model/download
  → WhisperModelService.start_download(size from config)
       → Hugging Face snapshot → data/whisper-models/<size>/
       → WhisperRuntime.load_size(size) → app.state.whisper_model
User → GET /speech/model/status (HTMX poll while downloading)
```

Configured size and locale live in `data/config.json` (`ProviderConfig`). Transcription `language` follows the interview locale snapshot, not live config changes mid-session.

## Data Flow: Complete Interview

```
Client → WS {"type":"complete"}
  → InterviewCompletionService.complete_interview(interview_id)
       → build Q&A summary → AI overall evaluation
       → UnitOfWork: save overall_feedback, mark completed, set score
       → returns [EvaluatingEvent, InterviewCompletedEvent]
  → events_to_messages() → client
```

## Data Access Pattern

```python
from app.domain.interview_lifecycle import compute_interview_score
from app.models import Interview
from app.uow import UnitOfWork

with UnitOfWork(auto_commit=True) as uow:
    interview = Interview(id=..., level=..., status="active", ...)
    uow.interviews.add(interview)
    for answer in answers:
        uow.answers.add(answer)

with UnitOfWork(auto_commit=True) as uow:
    db_interview = uow.interviews.get(interview_id)
    score = compute_interview_score(db_interview)
    uow.interviews.mark_completed(db_interview, score)
```

`InterviewRepository.get()` eagerly loads `answers` via `selectinload`. Prefer `UnitOfWork` in services for all transactional work.

## Scoring

- Each answered round (initial or follow-up) is scored **1–5** by the AI.
- Maximum points per round: `MAX_SCORE_PER_ROUND` (5) in `app/domain/interview_lifecycle.py`.
- Session total: `compute_interview_score()` sums all non-null answer scores.
- Per-question breakdown: `build_per_question_score_breakdown()` for completion feedback.

## Persistence & Configuration

| Path | Purpose |
|------|---------|
| `data/db/grillkit.db` | SQLite database (`DATABASE_URL` in `database.py`) |
| `data/config.json` | AI provider, `locale`, `speech_model_size` (`ConfigService`) |
| `data/whisper-models/<size>/` | Offline faster-whisper snapshots (`WhisperModelService`) |
| `data/questions/{language}/{level}/{category}.yaml` | Question banks |

Docker Compose mounts `./data:/app/data` so DB and config survive container restarts. `init_db()` runs on app startup (`lifespan` in `main.py`).

## Question Banks

Current YAML banks under `data/questions/`:

- **python** — junior / middle / senior (multiple categories per level)
- **database** — junior / middle / senior (SQL, design, NoSQL, etc.)

`questions.py` discovers languages and categories from the filesystem. Setup uses `GET /setup/options` for cascaded form updates.

## Current Limitations

- Only one AI adapter type is implemented: `openai-compatible` (`ProviderFactory`)
- Preset provider names in UI/docs may list OpenAI, Anthropic, Ollama, etc., but all use the same HTTP client shape
- Interview interaction for answers is WebSocket-only (`GET` page + `WS /interview/{id}/ws`)
- Per-round scores and feedback are stored during the interview but shown in the UI only after completion (WebSocket `feedback` advances questions without score bubbles)
- AI follow-ups: up to `InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH` (2) extra rounds per question
- YAML fields `follow_ups` and `expected_points` are loaded but not used for scoring (follow-ups are AI-generated)
- Deleting or resetting `data/db/grillkit.db` is required when ORM schema changes locally (no migrations yet)
- Speech: offline Whisper only; model and download progress are **per process** (not shared across multiple uvicorn workers)
- Dictation returns a **single final transcript** on stop (no streaming `partial` messages)
