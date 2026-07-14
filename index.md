---
layout: default
title: GrillKit
description: Open-source, self-hosted AI technical interview trainer. Practice theory Q&A, live coding, or both — with structured scoring and a local results history.
theme: jekyll-theme-cayman
---

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/License-Apache%202.0-yellow.svg" alt="Apache 2.0" />
  <img src="https://img.shields.io/badge/self--hosted-Docker-2496ED.svg" alt="Self-hosted with Docker" />
</p>

<p align="center">
  <strong>
    <a href="#why-grillkit">Why GrillKit</a> ·
    <a href="#quick-start">Quick Start</a> ·
    <a href="#features">Features</a> ·
    <a href="https://github.com/GrillKit/grillkit">GitHub Repo →</a>
  </strong>
</p>

GrillKit is an open-source, self-hosted AI interview trainer. Practice **theory Q&A**, **live coding**, or **both in one session**, drawn from curated question banks — with structured scoring, follow-up questions, optional voice, and a local results history. Bring your own LLM, cloud or local.

---

## Why GrillKit

A general chat assistant is flexible — but it doesn't run an *interview* for you. GrillKit turns ad-hoc prompting into a structured practice session.

| What you need | ChatGPT-style chat | GrillKit |
|---|---|---|
| Curated technical questions | You prompt each time | Built-in tracks (Python, Kafka, System Design…), levels, and topics |
| Interview flow | Free-form thread | Fixed session with scoring (1–5), follow-ups, and a summary |
| Live coding practice | Paste code in chat | Monaco editor, run public tests, submit for hidden tests + AI review |
| Practice history | Scattered chats | Dashboard with past sessions and detailed review pages |
| Skip what you know | You repeat prompts | Mark questions as known and exclude them from future sessions |
| Time pressure | None | Optional per-round timer |
| Voice practice | Depends on the product | Offline Whisper dictation, optional Piper narration, audio answers |
| Where your data lives | Vendor cloud | Fully self-hosted — SQLite and files stay on your machine |

**Structured practice.** Pick tracks, difficulty, and topics — GrillKit builds a full session plan and scores you across it, not just a single prompt.

**Privacy by default.** Runs via Docker on your own laptop or server. API keys and interview history stay local. No account, no subscription — just your LLM provider of choice.

---

## See it in action

**Dashboard** — recent sessions and a quick way to start a new one.

**Interview setup** — choose question-bank tracks, levels, topics, and session options.

**Coding sessions** — a Monaco editor with public-test runs and AI-reviewed submissions.

**Theory sessions** — real-time Q&A with live scoring and a final evaluation.

*(Screenshots and a full walkthrough video are available in the [repository README](https://github.com/GrillKit/grillkit).)*

---

## Features

### Session modes
- **Theory only** — Q&A pulled from curated banks; type, dictate, or record your answers
- **Coding only** — programming tasks with an editor, run, and submit
- **Theory then coding** / **Coding then theory** — combined sessions in either order

### Practice tools
- **Theory Q&A** with AI scoring (1–5) and up to two follow-up questions per item
- **Live coding** with a Monaco editor, public-test runs, and AI-reviewed submissions (via Judge0)
- **Question banks** covering Python, Database/SQL, System Design, Kafka, RabbitMQ, Docker, Kubernetes, Observability, Airflow, and more — across junior, middle, and senior levels
- **Optional timers** per round, with expired rounds automatically scored 0
- **Voice support** — offline Whisper dictation and optional Piper text-to-speech for questions
- **Audio answers** for models that support audio input
- **Results hub** with full theory and coding review after each session
- **Known questions** — mark items you've mastered and exclude them from future sessions
- **Dashboard** of recent sessions, with direct links to results

---

## Quick start

Requires [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/), plus an API key for a cloud LLM provider or a local OpenAI-compatible server (Ollama, vLLM, etc.).

```bash
git clone https://github.com/GrillKit/grillkit.git
cd grillkit
docker compose up --build
```

Then open **http://localhost:8000**.

Want live coding sessions too? Start the optional Judge0 profile:

```bash
docker compose --profile coding up --build
```

### First-time flow
1. **Configure** your LLM provider on `/config` and pick an interview model.
2. **Start a new interview** on `/setup` — choose a mode, tracks, levels, and topics.
3. **Practice** — answer theory questions or work through coding tasks.
4. **Review** your results, section by section, once the session ends.

---

## Works with any OpenAI-compatible API

| Provider | Example base URL |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| Ollama | `http://localhost:11434/v1` |
| vLLM / others | your endpoint + `/v1` |

No vendor lock-in — swap providers anytime from the configuration page.

---

## Open source

GrillKit is free and open source, licensed under **Apache License 2.0**.

- **Repository:** [github.com/GrillKit/grillkit](https://github.com/GrillKit/grillkit)
- **Architecture docs:** see `ARCHITECTURE.md` in the repo
- **Contributing:** see `CONTRIBUTING.md` in the repo
- **Security issues:** please follow the process in `SECURITY.md` — no public issues for vulnerabilities

---

<p align="center"><sub>Built for developers who want to practice interviews the way they'd actually happen — structured, scored, and private.</sub></p>
