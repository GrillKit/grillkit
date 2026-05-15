---
description: Always read ARCHITECTURE.md first; read only necessary files
alwaysApply: true
---

# Architecture-First Rule

## 1. Read ARCHITECTURE.md First

Before making ANY changes or reading ANY source files, **always read [`ARCHITECTURE.md`](ARCHITECTURE.md) first**.

This document contains:
- The complete project map (every file and its purpose)
- Module dependency graphs
- Data flow diagrams (session creation, answering questions, follow-ups)
- Key model schemas (InterviewSession, Answer)
- Current limitations

## 2. Read Only What You Need

After reading ARCHITECTURE.md, **do NOT read all files**. Instead:
1. Plan which files need to change based on the architecture diagram
2. Read ONLY those files (and their direct dependencies)
3. If you need more context on a specific module, read just that module

**Example:** If modifying interview session creation:
- Read: `app/services/interview_session.py`
- Maybe: `app/models.py` (for schema reference)
- NO need: `app/ai/*`, `app/api/config.py`, `templates/config*.html`, `static/css/*`

## 3. Keep ARCHITECTURE.md Updated

When making significant changes:
- Update the project map if files are added/removed/renamed
- Update dependency graph if module relationships change
- Update data flow diagrams if flows change
- Update models section if schemas change
