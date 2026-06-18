# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for bank text resolution service."""

from unittest.mock import MagicMock, patch

import pytest

from app.interview.services.bank_text import (
    KnownQuestionView,
    _coding_text_index,
    _theory_text_index,
    _to_views,
    resolve_known_views,
)


def _fake_question(id: str, text: str):
    return MagicMock(id=id, text=text)


def _fake_task(id: str, text: str):
    return MagicMock(id=id, text=text)


class TestKnownQuestionView:
    """Tests for the KnownQuestionView dataclass."""

    def test_dataclass_fields(self) -> None:
        view = KnownQuestionView(id="q1", text="What is Python?")
        assert view.id == "q1"
        assert view.text == "What is Python?"
        assert view == KnownQuestionView(id="q1", text="What is Python?")

    def test_frozen_and_slotted(self) -> None:
        view = KnownQuestionView(id="q1", text="Q")
        with pytest.raises(AttributeError):
            view.id = "q2"  # type: ignore[misc]


class TestTheoryTextIndex:
    """Tests for _theory_text_index caching."""

    def test_builds_index_and_caches(self, monkeypatch) -> None:
        _theory_text_index.cache_clear()

        fake_question = _fake_question("q1", "What is a list?")
        monkeypatch.setattr(
            "app.interview.services.bank_text.theory_bank.list_tracks",
            lambda: ("python",),
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text.theory_bank.list_levels",
            lambda track: ("junior",),
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text.theory_bank.list_categories",
            lambda track, level: ("basics",),
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text.theory_bank.load_category",
            lambda track, level, category: (fake_question,),
        )

        # First call should build and cache
        result1 = _theory_text_index()
        assert result1 == {"q1": "What is a list?"}

        # Modify the mock to prove caching
        monkeypatch.setattr(
            "app.interview.services.bank_text.theory_bank.load_category",
            lambda track, level, category: (),
        )

        result2 = _theory_text_index()
        assert result2 == {"q1": "What is a list?"}


class TestCodingTextIndex:
    """Tests for _coding_text_index caching."""

    def test_builds_index_and_caches(self, monkeypatch) -> None:
        _coding_text_index.cache_clear()

        fake_task = _fake_task("cod-001", "Write a function.")
        monkeypatch.setattr(
            "app.interview.services.bank_text.coding_bank.list_tracks",
            lambda: ("python",),
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text.coding_bank.list_levels",
            lambda track: ("junior",),
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text.coding_bank.list_categories",
            lambda track, level: ("basics",),
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text.coding_bank.load_category",
            lambda track, level, category: (fake_task,),
        )

        result1 = _coding_text_index()
        assert result1 == {"cod-001": "Write a function."}

        monkeypatch.setattr(
            "app.interview.services.bank_text.coding_bank.load_category",
            lambda track, level, category: (),
        )

        result2 = _coding_text_index()
        assert result2 == {"cod-001": "Write a function."}


class TestToViews:
    """Tests for _to_views helper."""

    def test_maps_ids_to_views(self) -> None:
        index = {"q1": "Text one", "q2": "Text two"}
        views = _to_views(["q1", "q2"], index)
        assert len(views) == 2
        assert views[0] == KnownQuestionView(id="q1", text="Text one")
        assert views[1] == KnownQuestionView(id="q2", text="Text two")

    def test_uses_id_as_text_when_missing(self) -> None:
        index = {"q1": "Text one"}
        views = _to_views(["q1", "missing"], index)
        assert views[0] == KnownQuestionView(id="q1", text="Text one")
        assert views[1] == KnownQuestionView(id="missing", text="missing")

    def test_empty_item_ids(self) -> None:
        assert _to_views([], {"q1": "Text"}) == []


class TestResolveKnownViews:
    """Tests for resolve_known_views."""

    def test_builds_views_correctly(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.interview.services.bank_text._theory_text_index",
            lambda: {"q1": "Theory Q1"},
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text._coding_text_index",
            lambda: {"cod-001": "Coding T1"},
        )

        grouped = {
            "theory": ["q1", "missing-theory"],
            "coding": ["cod-001"],
        }
        result = resolve_known_views(grouped)

        assert len(result["theory"]) == 2
        assert result["theory"][0] == KnownQuestionView(id="q1", text="Theory Q1")
        assert result["theory"][1] == KnownQuestionView(
            id="missing-theory", text="missing-theory"
        )

        assert len(result["coding"]) == 1
        assert result["coding"][0] == KnownQuestionView(
            id="cod-001", text="Coding T1"
        )

    def test_handles_empty_groups(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.interview.services.bank_text._theory_text_index",
            lambda: {},
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text._coding_text_index",
            lambda: {},
        )

        result = resolve_known_views({"theory": [], "coding": []})
        assert result == {"theory": [], "coding": []}

    def test_handles_missing_branch_keys(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.interview.services.bank_text._theory_text_index",
            lambda: {},
        )
        monkeypatch.setattr(
            "app.interview.services.bank_text._coding_text_index",
            lambda: {},
        )

        result = resolve_known_views({"theory": ["q1"]})
        assert result["theory"] == [KnownQuestionView(id="q1", text="q1")]
        assert result["coding"] == []
