# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Canonical filesystem paths for GrillKit data and assets."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_PATH = DATA_DIR / "config.json"
LLM_MODELS_PATH = DATA_DIR / "llm_models.json"
WHISPER_MODELS_ROOT = DATA_DIR / "whisper-models"
PIPER_VOICES_ROOT = DATA_DIR / "piper-voices"
TTS_CACHE_DIR = DATA_DIR / "tts-cache"
QUESTIONS_DIR = DATA_DIR / "questions"
DB_DIR = DATA_DIR / "db"
STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
