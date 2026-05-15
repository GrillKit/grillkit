# GrillKit Architecture

## Project Map

```
grillkit/
├── app/
│   ├── main.py                 # FastAPI app factory, lifespan, router registration
│   ├── database.py             # Engine, SessionLocal, Base, init_db()
│   ├── models.py               # SQLAlchemy models: InterviewSession, Answer
│   ├── questions.py            # YAML question loader: Question dataclass, load_category()
│   ├── ai/                     # AI provider abstractions
│   │   ├── base.py             # AIProvider ABC, Message, GenerationResult
│   │   ├── factory.py          # ProviderFactory.from_config()
│   │   └── openai_compatible.py # OpenAICompatibleProvider (single impl)
│   ├── api/                    # FastAPI routers
│   │   ├── __init__.py         # Re-exports all routers
│   │   ├── root.py             # GET / → dashboard or setup redirect
│   │   ├── setup.py            # GET/POST /setup → interview config + session creation
│   │   ├── config.py           # GET/POST/DELETE /config → AI provider settings
│   │   └── interview.py        # GET /interview/{id}, POST /interview/{id}/answer
│   └── services/               # Business logic layer
│       ├── config.py           # ConfigService: get/save/delete config, test_connection
│       └── interview_session.py # InterviewSessionService: CRUD, answers, follow-ups
├── templates/                  # Jinja2 templates
│   ├── base.html               # Layout: navbar, main content block, dark/light theme
│   ├── dashboard.html          # Home page with quick stats
│   ├── setup.html              # Interview config form (topic, level, question count)
│   ├── config.html             # AI provider settings page
│   ├── config_form.html        # Config form partial (provider, URL, model, key)
│   ├── config_success.html     # Config saved confirmation
│   ├── config_test_result.html # Connection test result partial
│   └── interview.html          # Chat view: question → answer → feedback bubbles
├── static/
│   └── css/
│       └── styles.css          # 650+ lines: layout, cards, forms, chat bubbles, dark mode
├── data/
│   ├── db/                     # SQLite database location (gitignored)
│   ├── config.json             # AI provider configuration (gitignored)
│   └── questions/              # YAML question banks
│       └── python/
│           ├── junior/         # data-structures.yaml (2 questions)
│           ├── middle/         # (empty)
│           └── senior/         # (empty)
└── tests/                      # pytest suite (75 tests)
    ├── test_ai_base.py         # Message, GenerationResult, AIProvider ABC
    ├── test_ai_factory.py      # ProviderFactory
    ├── test_openai_compatible.py # OpenAICompatibleProvider (mock HTTP)
    ├── test_api_routers.py     # Root, config endpoints
    ├── test_config_service.py  # ConfigService, ProviderConfig
    ├── test_database.py        # InterviewSession model
    ├── test_main.py            # App factory, lifespan
    ├── test_questions.py       # YAML loader
    └── test_session.py         # (empty stub)
```

## Module Dependency Graph

```
main.py
├── database.py (init_db)
├── api/__init__.py
│   ├── root.py → services/config.py
│   ├── setup.py → services/interview_session.py → database.py, models.py, questions.py
│   ├── config.py → services/config.py → ai/factory.py
│   └── interview.py → services/interview_session.py → database.py, models.py
└── services/config.py → ai/factory.py → ai/openai_compatible.py → ai/base.py
```

## Data Flow: Interview Session Creation

```
Browser → POST /setup {topic: "python", level: "junior", count: 5}
  → setup.py → InterviewSessionService.create_session()
    → questions.load_category("python", "junior", ...)  # load from YAML
    → shuffle + pick N questions
    → create InterviewSession row in SQLite
    → create N Answer rows (round=0, answer_text=NULL)
  ← 303 Redirect → /interview/{session_id}
```

## Data Flow: Answering Questions

```
Browser → GET /interview/{session_id}
  → interview.py → InterviewSessionService.get_session()
    → SELECT interview_session + eager load answers (selectinload)
    → find first answer with round=0 AND answer_text IS NULL
  ← render interview.html with chat history + answer form

Browser → POST /interview/{session_id}/answer {question_id, answer_text}
  → interview.py → InterviewSessionService.submit_answer()
    → UPDATE answer SET answer_text = ... WHERE session_id AND question_id AND round=0
  ← 303 Redirect → /interview/{session_id}
```

## Key Models

### InterviewSession
```
id: str (UUID)          — primary key
level: str              — junior/middle/senior
category: str           — python/algorithms/...
question_count: int     — number of questions (default 5)
question_ids: str       — JSON list of YAML question IDs in display order
status: str             — active/completed
score: int | None       — summed from answered questions
started_at: datetime
completed_at: datetime | None
answers: [Answer]       — relationship sorted by (order, round)
```

### Answer
```
id: int (auto)          — primary key
interview_session_id: str (FK) — parent session
question_id: str        — YAML question ID (e.g., "ds-001")
order: int              — 1-based display order
round: int              — 0 = initial, 1+ = follow-up
question_text: str      — snapshot of question at time of asking
question_code: str | None
answer_text: str | None — user's answer (NULL until answered)
score: int | None       — AI evaluation (1-5), NULL until evaluated
feedback: str | None    — AI feedback text
created_at: datetime
```

## Follow-up Flow

When AI decides user's answer is insufficient:

```
InterviewSessionService.add_follow_up(session_id, question_id, "Deeper question text...")
  → creates new Answer row with same order, round + 1, answer_text=NULL
  → user sees this as the "current question" on next page load
```

Sort order for chat display: `(order ASC, round ASC)`

```
1.0: "What's the difference?" → user answer → AI score
1.1: "And what about performance?" → user answer → AI score  (follow-up)
2.0: "How does dict work?" → user answer → AI score
```

## Current Limitations

- Only one AI provider implemented (`openai-compatible`)
- Only Python junior questions (1 category, 2 questions)
- No AI evaluation yet (score/feedback always NULL)
- No WebSocket — HTTP POST redirects for each answer
- No interview history page
- Empty test files: `test_session.py`
