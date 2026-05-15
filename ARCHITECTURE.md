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
│   │   └── interview.py        # GET /interview/{id}, POST /interview/{id}/answer, /complete
│   └── services/               # Business logic layer
│       ├── config.py           # ConfigService: get/save/delete config, test_connection
│       ├── interview_session.py # InterviewSessionService: CRUD, answers, follow-ups, AI orchestration
│       └── interview_evaluator.py # InterviewEvaluatorService: AI prompts, Pydantic models, parsing
├── templates/                  # Jinja2 templates
│   ├── base.html               # Layout: navbar, main content block, dark/light theme
│   ├── dashboard.html          # Home page with quick stats
│   ├── setup.html              # Interview config form (topic, level, question count)
│   ├── config.html             # AI provider settings page
│   ├── config_form.html        # Config form partial (provider, URL, model, key)
│   ├── config_success.html     # Config saved confirmation
│   ├── config_test_result.html # Connection test result partial
│   └── interview.html          # Chat view: question → answer → feedback + final evaluation
├── static/
│   └── css/
│       └── styles.css          # 650+ lines: layout, cards, forms, chat bubbles, dark mode, score table
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
│                                       ↕ (orchestration)
│                           services/interview_evaluator.py → ai/base.py (Message, AIProvider)
│                           services/config.py (create_provider_from_config)
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

## Data Flow: Answering Questions (with AI Evaluation)

```
Browser → GET /interview/{session_id}
  → interview.py → InterviewSessionService.get_session()
    → SELECT interview_session + eager load answers (selectinload)
    → find first answer with answer_text IS NULL (any round)
  ← render interview.html with chat history + answer form

Browser → POST /interview/{session_id}/answer {question_id, answer_text}
  → interview.py → InterviewSessionService.process_answer_submission()
    1. Save answer_text to DB
    2. Create AI provider from saved config (ConfigService)
    3. If round=0 → InterviewEvaluatorService.evaluate_answer()
       → AI returns {score, feedback, follow_up_needed, follow_up_question}
       → Save score + feedback to Answer
       → If follow_up_needed → InterviewSessionService.add_follow_up()
    4. If round>=1 → InterviewEvaluatorService.evaluate_follow_up()
       → AI returns {score, feedback, needs_further_follow_up, follow_up_question}
       → Save score + feedback to Answer
       → If needs_further_follow_up & round < 2 → add_follow_up()
  ← 303 Redirect → /interview/{session_id}
```

## Data Flow: Session Completion (with AI Summary)

```
Browser → POST /interview/{session_id}/complete
  → interview.py → InterviewSessionService.process_session_completion()
    1. Collect all answered Q&A pairs
    2. Create AI provider
    3. InterviewEvaluatorService.evaluate_session()
       → AI returns {overall_feedback, topics_to_review, strengths_summary, score_breakdown}
    4. Save evaluation JSON to InterviewSession.overall_feedback
    5. InterviewSessionService.complete_session() — set status="completed", sum scores
  ← 303 Redirect → /interview/{session_id} (now shows final evaluation section)
```

## AI Evaluation Architecture

### Pydantic Models for Structured Output

Each AI call uses a Pydantic model with JSON schema embedded in the system prompt:

| Model | Used For | Key Fields |
|-------|----------|------------|
| `AnswerEvaluation` | Initial answer (round=0) | score, feedback, strengths, weaknesses, follow_up_needed, follow_up_question |
| `FollowUpEvaluation` | Follow-up answer (round>=1) | score, feedback, needs_further_follow_up, follow_up_question |
| `SessionEvaluation` | Entire session | overall_feedback, topics_to_review, strengths_summary, score_breakdown |

### Prompt Strategy

```
For each answer evaluation:
  system: [instructions + Pydantic JSON schema]
  user:   "Question:\n{text}\n\nAnswer:\n{text}"

For each follow-up:
  system: [instructions + Pydantic JSON schema]
  user:   "Original Question:\n...\nInitial Answer:\n...\nFollow-up Question:\n...\nFollow-up Answer:\n..."

For session evaluation:
  system: [instructions + Pydantic JSON schema]
  user:   "Interview Level: ...\nCategory: ...\n\nQuestions and Answers:\n{all Q&A pairs}"
```

### Follow-up Depth

Maximum 2 follow-up rounds per question (round=0, 1, 2). Controlled by `InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH = 2`.

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
overall_feedback: str | None — JSON string with final evaluation data
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

When AI decides user's answer is insufficient (score <= 3):

```
InterviewSessionService.add_follow_up(session_id, question_id, "Deeper question text...")
  → creates new Answer row with same order, round + 1, answer_text=NULL
  → user sees this as the "current question" on next page load
```

Sort order for chat display: `(order ASC, round ASC)`

```
1.0: "What's the difference?" → user answer → AI score + feedback
1.1: "And what about performance?" → user answer → AI score + feedback  (follow-up)
2.0: "How does dict work?" → user answer → AI score + feedback
```

## Service Layer Structure

| Service | Responsibility |
|---------|---------------|
| `ConfigService` | CRUD for AI provider config (`data/config.json`), provider creation |
| `InterviewSessionService` | DB operations (CRUD sessions & answers) + orchestration of AI evaluation |
| `InterviewEvaluatorService` | AI interaction: Pydantic models, system prompts, JSON parsing |

## Current Limitations

- Only one AI provider implemented (`openai-compatible`)
- Only Python junior questions (1 category, 2 questions)
- No WebSocket — HTTP POST redirects for each answer
- No interview history page
- Empty test files: `test_session.py`
- AI evaluation is synchronous — user waits for AI response on each answer
- Error in AI evaluation returns 502 error to user (no graceful degradation yet)
