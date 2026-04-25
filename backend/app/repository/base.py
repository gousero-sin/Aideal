"""Repository base e abstrações."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """Interface base para repositories."""

    @abstractmethod
    def get_by_id(self, id: Any) -> T | None:
        """Busca entidade por ID."""
        pass

    @abstractmethod
    def create(self, entity: T) -> T:
        """Cria nova entidade."""
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """Atualiza entidade existente."""
        pass

    @abstractmethod
    def delete(self, id: Any) -> bool:
        """Remove entidade por ID."""
        pass
