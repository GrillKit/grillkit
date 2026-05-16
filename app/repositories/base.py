# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Abstract repository interface and SQLAlchemy base implementation.

Defines a generic ``Repository[T]`` protocol that all concrete
repositories must satisfy, plus an ``SqlAlchemyRepository`` base
class that eliminates boilerplate for common CRUD operations.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Abstract protocol (interface)
# ---------------------------------------------------------------------------


class Repository(ABC, Generic[T]):
    """Generic repository interface for data access.

    All repositories in the system must implement these methods,
    which keeps the service layer decoupled from the underlying
    storage technology.
    """

    @abstractmethod
    def add(self, entity: T) -> T:
        """Register a new entity for insertion.

        Args:
            entity: The entity instance to persist.

        Returns:
            The same entity with an assigned identity (if auto-generated).
        """

    @abstractmethod
    def get(self, entity_id: str) -> T | None:
        """Retrieve a single entity by its primary key.

        Args:
            entity_id: The primary key value.

        Returns:
            The entity or None if not found.
        """

    @abstractmethod
    def list_all(self) -> Sequence[T]:
        """Return all entities of this type."""


# ---------------------------------------------------------------------------
# SQLAlchemy base implementation
# ---------------------------------------------------------------------------


class SqlAlchemyRepository(Repository[T], ABC):
    """SQLAlchemy-backed repository base.

    Subclasses must set ``_model`` to the SQLAlchemy model class.
    """

    _model: type[T]  # set by subclass

    def __init__(self, session: Session) -> None:
        """Initialize the repository with an active DB session.

        Args:
            session: An active SQLAlchemy Session.
        """
        self._session = session

    def add(self, entity: T) -> T:
        """Add an entity to the session (no flush).

        Args:
            entity: The model instance to persist.

        Returns:
            The same instance (caller may refresh later).
        """
        self._session.add(entity)
        return entity

    def get(self, entity_id: str) -> T | None:
        """Get entity by string primary key.

        Args:
            entity_id: The primary key value.

        Returns:
            The entity or None.
        """
        return self._session.get(self._model, entity_id)

    def list_all(self) -> Sequence[T]:
        """Return all rows for this model.

        Returns:
            A list of model instances.
        """
        return self._session.query(self._model).all()