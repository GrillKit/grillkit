# GrillKit Architecture

User-facing overview, screenshots, and quick start: [README.md](README.md).

GrillKit is an AI-powered technical interview trainer. The stack is **FastAPI** (HTTP + WebSocket), **SQLAlchemy** (SQLite), **Alembic** (schema and data migrations), **Jinja2** templates, and **OpenAI-compatible** plus **faster-whisper** adapters in `ai/`. Code is organized **by feature** (`interview/`, `speech/`, `question_voice/`, `platform/`) with cross-cutting code in `shared/`. Within each feature: transport in `api/`, orchestration in `services/`, Pydantic read models in `schemas/` (where present), feature rules in `services/rules/`, persistence in `repositories/` (interview only). Interview transactions use `InterviewUnitOfWork` (`interview/repositories/uow.py`), extending base `UnitOfWork` in `shared/infrastructure/`. The interview API maps ORM rows to `interview/schemas/` before HTTP/WebSocket responses; it does not expose SQLAlchemy models on the wire.

## Terminology

| Term | Meaning | Examples |
|------|---------|----------|
| **locale** | Language for AI feedback, follow-ups, and speech dictation | `en`, `ru` — stored on `Interview.locale` and `AppConfig` |
| **track** | Question bank slug (top-level directory under `data/questions/`) | `python`, `database`, `system-design` |
| **level** | Difficulty tier within a track | `junior`, `middle`, `senior` |
| **category** | Topic YAML file within a track/level | `basics`, `redis`, `system-design` |

## Project Map

```
grillkit/
├── app/
│   ├── main.py                 # create_app(), router registration, lifespan → run_migrations()
│   ├── paths.py                # PROJECT_ROOT, DATA_DIR, CONFIG_PATH, whisper/questions/db paths
│   ├── questions.py            # YAML question loader (data/questions/)
│   ├── templating.py           # Shared Jinja2Templates + static_version()
│   ├── shared/
│   │   ├── exceptions.py       # Cross-feature domain errors
│   │   ├── locales.py          # SUPPORTED_LOCALES, normalize_locale()
│   │   ├── infrastructure/
│   │   │   ├── database.py     # engine, SessionLocal, DATABASE_URL env, run_migrations()
│   │   │   ├── models.py       # Interview, Answer ORM models
│   │   │   ├── audio_wav.py    # Canonical mono 16 kHz WAV validation
│   │   │   └── uow.py          # Base UnitOfWork: session, commit, rollback
│   │   └── repositories/
│   │       └── base.py         # Repository[T], SqlAlchemyRepository[T]
│   ├── ai/
│   │   ├── base.py             # AIProvider protocol
│   │   ├── speech_transcriber.py  # SpeechTranscriber protocol (offline dictation)
│   │   ├── audio_probe.py      # Minimal WAV bytes for connectivity / audio tests
│   │   ├── factory.py          # ProviderFactory.from_config()
│   │   ├── llm_models.py       # Catalog entry types (incl. accepts_audio_input)
│   │   ├── openai_compatible.py
│   │   └── faster_whisper_transcriber.py
│   ├── platform/
│   │   ├── schemas.py          # Config page read models, NewLLMModel, mappers
│   │   ├── api/
│   │   │   ├── config.py       # GET/POST /config + build_config_page_context
│   │   │   ├── llm_page_context.py
│   │   │   ├── runtime_reload.py # SpeechRuntimeCoordinator hooks
│   │   │   └── deps.py
│   │   └── services/
│   │       ├── config.py       # AppConfig, ConfigService (data/config.json)
│   │       ├── llm_catalog.py  # data/llm_models.json load/save/select
│   │       ├── speech_runtime.py  # SpeechRuntimeCoordinator (Whisper + Piper lifecycle)
│   │       ├── speech_settings.py
│   │       └── ai_context.py   # ai_provider_from_config() async context manager
│   ├── interview/
│   │   ├── schemas/            # InterviewRead, page context, WebSocket message models
│   │   ├── services/rules/     # progress, lifecycle, selection, timer (pure rules)
│   │   ├── repositories/
│   │   │   ├── interview.py
│   │   │   ├── answer.py
│   │   │   └── uow.py          # InterviewUnitOfWork
│   │   ├── services/
│   │   │   ├── creation.py
│   │   │   ├── question_planning.py  # YAML plan + validation
│   │   │   ├── query.py
│   │   │   ├── page.py         # Interview page context (dictation, audio-answer flags)
│   │   │   ├── dashboard.py
│   │   │   ├── completion.py
│   │   │   ├── answer_processing.py  # WS orchestration (submit + timeout)
│   │   │   ├── answer_timer.py
│   │   │   ├── answer_ai_evaluation.py
│   │   │   ├── answer_evaluation_persistence.py
│   │   │   ├── session_navigation.py
│   │   │   ├── events.py
│   │   │   └── evaluator/      # service.py, models.py, prompts.py
│   │   └── api/
│   │       ├── deps.py         # Services + AIProvider for WS
│   │       ├── access.py       # Cross-feature InterviewView reads
│   │       ├── dashboard.py    # GET /
│   │       ├── setup.py        # GET/POST /setup, GET /setup/options
│   │       ├── setup_form.py
│   │       ├── routes.py       # GET /interview/{id}, question-audio, audio-answer, WS
│   │       ├── ws_protocol.py  # InterviewEvent → JSON (uses interview/schemas/ws.py)
│   │       └── errors.py
│   ├── question_voice/
│   │   ├── api/
│   │   │   └── routes.py       # GET /speech/tts/status, POST /speech/tts/voice/download
│   │   └── services/           # piper_*, tts_cache, question_audio, rules (voices)
│   ├── speech/
│   │   ├── schemas/            # Pydantic status/page context read models
│   │   ├── services/           # whisper_*, dictation
│   │   └── api/
│   │       ├── routes.py       # GET/POST /speech/model/*
│   │       ├── preload.py
│   │       ├── dictation.py    # WS /interview/{id}/dictation
│   │       └── dictation_protocol.py
├── templates/                  # Jinja2 HTML (dashboard, setup, config, interview, speech_model_*)
├── static/
│   ├── css/styles.css
│   └── js/                     # dictation, interview_voice, interview_timer, interview_audio_answer, ...
├── data/
│   ├── config.json             # Locale, speech/TTS flags (gitignored)
│   ├── llm_models.json         # User LLM catalog + selected model (gitignored)
│   ├── whisper-models/<size>/  # faster-whisper snapshots (gitignored content)
│   ├── piper-voices/<voice_id>/
│   ├── tts-cache/v2/{locale}/
│   ├── db/grillkit.db
│   └── questions/              # YAML banks: {track}/{level}/{category}.yaml
├── alembic/                    # Schema and data migrations
├── alembic.ini
├── docker-compose.yml          # app service only
├── docker-entrypoint.sh        # PUID/PGID, ensures data/db writable
├── Dockerfile                  # Multi-stage uv build → uvicorn
└── tests/
```

## HTTP Routes

| Method | Path | Module | Purpose |
|--------|------|--------|---------|
| GET | `/` | `interview/api/dashboard.py` | Interview history (last 20) |
| GET | `/setup` | `interview/api/setup.py` | New interview form (redirects to `/config` if unset) |
| POST | `/setup` | `interview/api/setup.py` | Create interview → redirect `/interview/{id}` |
| GET | `/setup/options` | `interview/api/setup.py` | Cascaded JSON: tracks → levels → categories |
| GET | `/config` | `platform/api/config.py` | AI provider configuration form |
| POST | `/config` | `platform/api/config.py` | Test connection (via form dependency), then save |
| POST | `/config/test` | `platform/api/config.py` | Test connection without saving |
| POST | `/config/llm-models` | `platform/api/config.py` | Add catalog entry (incl. `accepts_audio_input`) |
| DELETE | `/config` | `platform/api/config.py` | Remove saved provider configuration |
| GET | `/speech/model/status` | `speech/api/routes.py` | Whisper model install status (HTML or JSON) |
| POST | `/speech/model/download` | `speech/api/routes.py` | Start Whisper download for `config.speech_model_size` |
| GET | `/speech/model/options` | `speech/api/routes.py` | JSON size trade-off metadata |
| GET | `/speech/tts/status` | `question_voice/api/routes.py` | Piper voice status (HTML fragment or JSON) when question voice is enabled |
| POST | `/speech/tts/voice/download` | `question_voice/api/routes.py` | Start Piper voice download for configured `tts_voice_id` |
| GET | `/interview/{interview_id}` | `interview/api/routes.py` | Interview page (active or completed) |
| GET | `/interview/{interview_id}/question-audio` | `interview/api/routes.py` | WAV for current question text (`question_id`, `round` query params) |
| POST | `/interview/{interview_id}/audio-answer` | `interview/api/routes.py` | Multipart WAV answer → NDJSON (`saved`, `transcript`, `feedback`, …) |
| WS | `/interview/{interview_id}/ws` | `interview/api/routes.py` | Real-time text answers and completion |
| WS | `/interview/{interview_id}/dictation` | `speech/api/dictation.py` | PCM dictation: `start` → `ready`, audio chunks, `stop` → `final` |
| — | `/static/*` | `main.py` | CSS, JS, and assets |

## Layer Responsibilities

| Package / layer | Responsibility |
|-----------------|----------------|
| `interview/api/`, `speech/api/`, `platform/api/`, `question_voice/api/` | HTTP/WebSocket transport, forms, template rendering |
| `*/api/deps.py` | Inject service **classes** via `Depends` (handlers call static methods) |
| `interview/schemas/` | Pydantic read models (`InterviewRead`, page context, WS server messages) |
| `interview/api/ws_protocol.py` | Map `InterviewEvent` dataclasses → interview WebSocket JSON (`interview/schemas/ws.py`) |
| `speech/api/dictation_protocol.py` | Dictation WebSocket message types (`start`, `stop`, `ready`, `final`, `error`) |
| `interview/api/errors.py` | Map `InterviewDomainError` → error payloads |
| `*/services/` | Use-case orchestration (static methods on service classes) |
| `*/services/rules/` | Pure rules (no I/O) for a feature (timer, selection, voices, etc.) |
| `shared/exceptions.py`, `shared/locales.py` | Cross-cutting exceptions and locale helpers |
| `interview/repositories/` | Interview persistence (SQLAlchemy via `SqlAlchemyRepository`) |
| `shared/infrastructure/uow.py` | Base transaction boundary (session lifecycle) |
| `interview/repositories/uow.py` | `InterviewUnitOfWork`: `uow.interviews`, `uow.answers` |
| `shared/infrastructure/models.py` | ORM models |
| `ai/` | Provider adapters (`AIProvider`, `SpeechTranscriber`) |
| `questions.py` | Read-only YAML question bank access |

Application services are **stateless classes with `@staticmethod`**. FastAPI dependencies in each feature's `deps.py` return the class (e.g. `InterviewQuery`), not instances.

## Module Dependency Graph

Dependencies flow **downward** (caller → callee). Plain-text diagram for editors that do not render Mermaid.

```
main.py ──► lifespan: init_db(), SpeechRuntimeCoordinator.startup() (Whisper + Piper when configured)
  ├── interview/api/  (dashboard, setup, routes)
  │     ├── routes.py ──► ws_protocol, errors, speech/services/page, question_voice/services/page
  │     └── deps.py ──► interview/services/*
  ├── platform/api/config.py ──► platform/services/config, platform/services/page
  ├── question_voice/api/routes.py ──► piper_voice, tts_cache
  └── speech/api/  (routes, dictation)
        ├── dictation.py ──► dictation_protocol, dictation session, app.state.speech_transcriber
        └── routes.py ──► speech/services/whisper_model

interview/api/routes.py ──► question_voice/services/question_audio, interview/api/deps (AIProvider)
interview/api/access.py ──► interview/services/query, interview/schemas/interview (InterviewRead)

platform/api/runtime_reload.py ──► platform/services/speech_runtime (SpeechRuntimeCoordinator)

question_voice/services/
  ├── question_audio.py ──► interview/api/access, speech_settings, tts_cache
  ├── piper_voice.py ──► Hugging Face download into data/piper-voices/
  ├── piper_runtime.py ──► in-process PiperVoice load and synthesis
  └── tts_cache.py ──► data/tts-cache/v2/{locale}/

interview/services/
  ├── creation.py ──► services/rules, question_planning, InterviewUnitOfWork
  ├── question_planning.py ──► app/questions.py, services/rules/selection
  ├── session_navigation.py ──► answer_timer, services/rules/progress, services/rules/timer
  ├── query.py ──► services/rules, InterviewUnitOfWork, dashboard, services/rules/timer
  ├── completion.py ──► evaluator, uow (AIProvider via interview/api/deps)
  ├── answer_processing.py ──► answer_timer, answer_ai_evaluation, answer_evaluation_persistence
  ├── answer_timer.py ──► services/rules/timer
  └── answer_ai_evaluation.py ──► evaluator (AIProvider injected)

interview/api/deps.py ──► platform/services/ai_context (yields AIProvider for WS/routes)

platform/services/config.py ──► ai/factory, speech/schemas, data/config.json
speech/services/
  ├── whisper_model.py ──► whisper_runtime, whisper_storage, Hugging Face hub
  ├── whisper_runtime.py ──► ai/faster_whisper_transcriber, whisper_storage
  └── dictation.py ──► ai/speech_transcriber

shared/infrastructure/uow.py
  └── interview/repositories/ (interview, answer) ──► shared/repositories/base, models
```

On GitHub, the same graph is also available as Mermaid (rendered on github.com only):

<details>
<summary>Mermaid source (GitHub preview)</summary>

```mermaid
flowchart TB
  main --> api_layer
  main --> whisper_runtime
  subgraph interview_api [interview/api]
    dashboard
    setup
    interview_routes[routes]
    interview_deps[deps]
    ws_protocol
    interview_errors[errors]
  end
  subgraph platform_api [platform/api]
    config_router[config]
  end
  subgraph speech_api [speech/api]
    speech_router[routes]
    dictation
    dictation_protocol
  end
  interview_routes --> interview_deps
  interview_routes --> ws_protocol
  interview_routes --> interview_errors
  interview_deps --> ai_context
  dictation --> dictation_protocol
  dictation --> dictation_svc[dictation session]
  dictation_svc --> speech_transcriber_proto[speech_transcriber]
  speech_router --> whisper_model
  whisper_runtime --> faster_whisper_transcriber
  subgraph interview_svc [interview/services]
    interview_creation[creation]
    interview_query[query]
    interview_completion[completion]
    answer_processing
    interview_evaluator[evaluator]
  end
  subgraph platform_svc [platform/services]
    config_service[config]
    ai_context
  end
  subgraph speech_svc [speech/services]
    whisper_model
    dictation_svc
  end
  faster_whisper_transcriber --> speech_transcriber_proto
  whisper_model --> whisper_runtime
  whisper_model --> whisper_storage
  whisper_runtime --> whisper_storage
  interview_svc --> interview_rules[services/rules]
  interview_svc --> uow
  interview_svc --> questions_mod[questions]
  interview_creation --> questions_mod
  interview_completion --> interview_evaluator
  answer_processing --> interview_evaluator
  ai_context --> config_service
  ai_context --> ai_layer
  subgraph ai_layer [ai]
    factory
    openai_compatible
    faster_whisper_transcriber
  end
  uow --> repos
  subgraph interview_repos [interview/repositories]
    interview_repo[interview]
    answer_repo[answer]
  end
  interview_repos --> models
```

</details>

## Naming Convention

| Concept | Name in code |
|---------|----------------|
| Interview ORM model | `Interview` (table `interviews`) |
| Primary key column | `Interview.id` (UUID string) |
| Route / WS path param | `interview_id` (same value as `Interview.id`) |
| Answer FK | `Answer.interview_id` → `interviews.id` |
| Create flow | `interview.services.creation.InterviewCreationService.create_interview()` |
| Read flow | `interview.services.query.InterviewQuery.get_interview()`, `list_dashboard_rows()` |
| Answer flow | `AnswerProcessingService` (orchestrates timer + `AnswerAiEvaluationService` + persistence) |
| Timeout flow | `AnswerProcessingService.stream_timeout_submission()` + `RoundTimerService` |
| Complete flow | `interview.services.completion.InterviewCompletionService.complete_interview()` |
| UoW repositories | `uow.interviews`, `uow.answers` |
| SQLAlchemy session | `uow.session` |

## Key Models

### Interview (`interviews`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | UUID v4 primary key |
| `locale` | `str` | AI feedback language (`en`, `ru`, …) |
| `selection_spec` | `str` | JSON `{sources: [{track, level, categories[]}]}` (required) |
| `question_count` | `int` | Number of questions in session |
| `question_ids` | `str` | JSON list of question IDs in display order |
| `question_time_limit_seconds` | `int \| None` | Per-round limit (`None` = timer off) |
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
| `started_at` | `datetime \| None` | When this round became active (timed sessions) |
| `score`, `feedback` | | After AI evaluation (1–5) or `0` on timeout |

Rows are created up front at interview creation (one per question, `round=0`). Follow-up rounds add new `Answer` rows via `AnswerRepository`.

## Data Flow: Configure Provider

```
User → GET /config → ConfigService.get_config() + LLMCatalogService.load_catalog()
User → POST /config/test → test selected catalog model (no save)
User → POST /config → merge form into config.json + catalog selection
  → ConfigService.test_connection(resolve_effective_config()) → AI provider ping
  → on success: save config.json and llm_models.json
User → POST /config/llm-models (add catalog entry, optional accepts_audio_input)
  → LLMCatalogService → data/llm_models.json
  → when accepts_audio_input: test text + audio capability + Whisper readiness
```

`ConfigService.resolve_effective_config()` applies the selected catalog entry’s `base_url`, `model`, and `api_key` for interviews and connection tests. Setup and interview flows require a saved config; otherwise `/setup` redirects to `/config`.

## Data Flow: Create Interview

```
User → POST /setup (selection_json, question_count, optional timer)
  → parse InterviewSelection (tracks, per-track level, topic categories)
  → validate question_count ≥ number of selected topics
  → locale from ConfigService.get_config() → Interview.locale snapshot
  → InterviewCreationService.create_interview(selection, …)
       → build_question_plan(): one question per topic, then proportional fill
       → questions grouped by track (form order), shuffled within each block
       → UnitOfWork(auto_commit=True): persist Interview + selection_spec + Answer rows
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
  → On the **last follow-up** of a question: advance to next question immediately;
       AI score/feedback for that round may persist in a background task (UI not blocked)
  → event_to_message() per event → client (not batched after evaluation)

Client → WS {"type":"timeout","question_id":"...","round":N}
  → AnswerProcessingService.stream_timeout_submission() when deadline passed
  → score 0, no AI, advance (same feedback shape with `timed_out: true`)

Client → WS {"type":"ping"}
  → InterviewQuery.get_interview() → {"type":"pong","status":"active"|"completed"|...}
```

**Server → client message types:** `saved`, `evaluating`, `transcript` (audio path), `feedback`, `interview_completed`, `error`, `pong`.

## Data Flow: Audio Answer (HTTP)

Requires active interview, catalog model with `accepts_audio_input`, and loaded Whisper (`app.state.speech_transcriber`).

```
Client → POST /interview/{id}/audio-answer (multipart: question_id, file=WAV)
  → validate mono 16 kHz PCM WAV (shared/infrastructure/audio_wav.py)
  → AnswerProcessingService.require_audio_answer_enabled()
  → transcribe via SpeechTranscriber → stream NDJSON (same event shapes as WS)
       → saved → transcript → evaluating → feedback (multimodal LLM when supported)
  → Client: static/js/interview_audio_answer.js
```

Gated on the interview page when dictation is available **and** `interview_model_accepts_audio` (`InterviewPageService` + catalog `accepts_audio_input`). Configuration save / add-model tests audio capability with `app/ai/audio_probe.py` when the flag is enabled.

## Data Flow: Dictation WebSocket

Separate from answer/evaluation WS. Requires active interview and loaded transcriber (`app.state.speech_transcriber`).

```
Client → WS connect /interview/{id}/dictation
  → InterviewQuery.get_interview() + require_active()
  → reject if model missing (download via /config → /speech/model/download)

Client → {"type":"start"}
  → DictationSession() → {"type":"ready"}

Client → binary PCM (16-bit LE mono, 16 kHz)
  → DictationSession.append_pcm()

Client → {"type":"stop"}
  → DictationSession.finalize(speech_transcriber, interview.locale)
  → {"type":"final","text":"..."} → connection closes
```

**Server → client message types:** `ready`, `final`, `error`.

## Data Flow: Speech Model Install

```
User → GET /config (speech_model_size, locale)
User → POST /speech/model/download
  → WhisperModelService.start_download(size from config)
       → Hugging Face snapshot → data/whisper-models/<size>/
       → WhisperRuntime.load_size(size) → app.state.speech_transcriber
User → GET /speech/model/status (HTMX poll while downloading)
```

Configured size and locale live in `data/config.json` (`AppConfig`). Transcription `language` follows the interview locale snapshot, not live config changes mid-session.

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
from app.interview.repositories.mappers import interview_read_to_domain

score = interview_read_to_domain(interview_read).total_score()
from app.shared.infrastructure.models import Interview
from app.interview.repositories.uow import InterviewUnitOfWork

with InterviewUnitOfWork(auto_commit=True) as uow:
    interview = Interview(id=..., selection_spec=..., status="active", ...)
    uow.interviews.add(interview)
    for answer in answers:
        uow.answers.add(answer)

with UnitOfWork(auto_commit=True) as uow:
    db_interview = uow.interviews.get(interview_id)
    score = compute_interview_score(db_interview)
    uow.interviews.mark_completed(db_interview, score)
```

`InterviewRepository.get()` eagerly loads `answers` via `selectinload`. Prefer `InterviewUnitOfWork` in interview services for all transactional work.

## Scoring

- Each answered round (initial or follow-up) is scored **1–5** by the AI.
- Maximum points per round: `MAX_SCORE_PER_ROUND` (5) in `app/interview/services/rules/lifecycle.py`.
- Session total: `compute_interview_score()` sums all non-null answer scores.
- Per-question breakdown: `build_per_question_score_breakdown()` for completion feedback.

## Persistence & Configuration

### Data directory

```
data/
├── config.json              # locale, speech/TTS flags, timer defaults (gitignored)
├── llm_models.json          # Interview model catalog + selected id (gitignored)
├── db/grillkit.db           # SQLite (gitignored; created on startup)
├── whisper-models/<size>/   # faster-whisper snapshots (gitignored content)
├── piper-voices/<voice_id>/ # Piper ONNX voices (gitignored content)
├── tts-cache/v2/{locale}/   # Cached question WAVs (gitignored content)
└── questions/               # YAML banks: {track}/{level}/{category}.yaml
```

| Path | Purpose |
|------|---------|
| `data/db/grillkit.db` | SQLite database (default; override with `DATABASE_URL`) |
| `data/config.json` | `locale`, `speech_model_size`, `question_voice_enabled`, `tts_voice_id`, timer defaults |
| `data/llm_models.json` | User LLM catalog entries and `selected` model id |
| `data/whisper-models/<size>/` | Offline faster-whisper snapshots (`WhisperModelService`) |
| `data/piper-voices/<voice_id>/` | Piper ONNX voice files (`PiperVoiceService`) |
| `data/tts-cache/v2/{locale}/` | Cached question WAVs (`TtsCacheService`; SHA-256 of normalized text) |
| `data/questions/{track}/{level}/{category}.yaml` | Question banks |

### Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy connection string (default: `sqlite:///<project>/data/db/grillkit.db`; Docker Compose uses `sqlite:////app/data/db/grillkit.db`) |
| `HF_TOKEN` | Hugging Face read token for Whisper/Piper downloads |
| `WHISPER_DEVICE` | `cpu` or `cuda` (default `cpu`) |
| `WHISPER_COMPUTE_TYPE` | `int8` or `float16` (default `int8` on CPU) |

Docker Compose mounts `./data:/app/data` so DB and config survive container restarts. `run_migrations()` runs on app startup (`lifespan` in `main.py`) via **Alembic** (`alembic upgrade head`). For a clean dev DB, remove `data/db/grillkit.db` and restart, or run `uv run alembic upgrade head` manually.

## Question Banks

Current top-level **tracks** under `data/questions/` (each has `junior` / `middle` / `senior` where applicable):

| Track | Focus |
|-------|--------|
| **python** | Language, frameworks (FastAPI, Django, …), asyncio, pytest, client libs |
| **database** | SQL, SQLite, Redis, migrations, ClickHouse, … |
| **system-design** | Language-agnostic scaling and distributed systems |
| **kafka** | Platform and streaming (plus Python client topics under `python/…/kafka.yaml`) |
| **rabbitmq** | Platform and Python client topics |
| **docker** | Images, operations, security |
| **kubernetes** | Fundamentals through production |
| **observability** | Prometheus, Grafana, Loki |
| **airflow** | Scheduling, executors, TaskFlow, operations |

`questions.py` discovers tracks and categories from the filesystem (`questions_map.yaml` is metadata only). Setup uses `GET /setup/options?track=…` for cascaded form updates.

### Localization (YAML)

User-facing strings use locale maps; metadata stays language-agnostic (see **Question voice (TTS)** below for audio behavior).

| Field | Shape | Notes |
|-------|-------|-------|
| `question.text` | `{en: "...", ru: "...", ...}` or legacy plain string (treated as `en`) | `load_category(..., locale)` resolves via `Interview.locale` at creation; snapshots on `Answer.question_text` |
| `question.code` | single string or null | Never localized |
| `follow_ups` | `{en: [...], ru: [...]}` or legacy list (treated as `en`) | Loaded for bank schema; not used at runtime (AI generates follow-ups) |
| `expected_points` | list | Loaded for bank schema; not used for scoring or prompts today |

Missing locale → `en` with a warning log. Supported codes: `app/shared/locales.py` (`en`, `ru`, `fr`, `es`, `de`). Banks are migrated incrementally; many categories still have `en` only.

`InterviewCreationService` passes `interview.locale` into the loader when creating answers.

## Question voice (TTS)

Optional offline Piper synthesis in the main app process.

| Topic | Implementation |
|-------|----------------|
| Config gate | `question_voice_enabled` in `data/config.json` |
| Voice id | `tts_voice_id` on `AppConfig` (default per locale in `question_voice/services/rules/voices.py`) |
| Voice files | `data/piper-voices/<voice_id>/` via `POST /speech/tts/voice/download` on `/config` |
| Synthesis | `PiperRuntime` in-process (`piper-tts` dependency) |
| App cache | `data/tts-cache/v2/{locale}/{sha256}.wav` via `TtsCacheService` |
| Audio route | `GET /interview/{id}/question-audio` — `question_text` snapshot only, never `question_code` |
| Status | `GET /speech/tts/status` — banners when voice is missing, downloading, or not loaded |
| UI | `static/js/interview_voice.js` auto-play + **Play question**; `question_voice_status.js` on `/config` |

Follow-up rounds use the same pipeline (cache key from localized `question_text` on the answer row).

## LLM model catalog

| Concern | Location |
|---------|----------|
| Catalog file | `data/llm_models.json` (gitignored) — models added via **Add model to catalog** on `/config` (`POST /config/llm-models`) |
| Loader | `app/platform/services/llm_catalog.py` |
| Selection | `selected` id in catalog JSON; `llm_preset_id` on resolved `AppConfig` |
| Audio flag | `accepts_audio_input` on `LLMModelEntry` — enables interview audio-answer UI and config audio probe |
| Effective config | `ConfigService.resolve_effective_config()` applies catalog `base_url`, `model`, and `api_key` |

## Current Limitations

- Only one AI adapter type is implemented: `openai-compatible` (`ProviderFactory`)
- Preset provider names in UI/docs may list OpenAI, Anthropic, Ollama, etc., but all use the same HTTP client shape
- Text answers use WebSocket (`WS /interview/{id}/ws`); spoken **audio answers** use `POST /interview/{id}/audio-answer` (NDJSON)
- Per-round scores and feedback are stored during the interview but shown in the UI only after completion (WebSocket `feedback` advances questions without live score bubbles)
- On the **last follow-up** of a question, navigation is immediate; that round’s score may finish persisting in the background
- AI follow-ups: up to `InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH` (2) extra rounds per question
- YAML fields `follow_ups` and `expected_points` are loaded but not used for scoring (follow-ups are AI-generated)
- Schema changes ship as Alembic revisions; startup runs `upgrade head` — for local experiments you can still delete `data/db/grillkit.db` and restart
- Speech: offline Whisper only; model and download progress are **per process** (not shared across multiple uvicorn workers)
- Dictation returns a **single final transcript** on stop (no streaming `partial` messages)
- Audio answers require a catalog model with `accepts_audio_input` and a loaded Whisper transcriber
- Question bank localization is partial: many YAML entries still fall back to `en` for non-English locales
- Question TTS: Piper voice must be downloaded on `/config` before synthesis; first load is per process (not shared across multiple uvicorn workers)
- Piper synthesis uses CPU ONNX; plan extra RAM on the host when question voice is enabled
