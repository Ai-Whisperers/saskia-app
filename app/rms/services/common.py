"""app/rms/services/common.py — Common service utilities."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Any
from sqlalchemy.orm import Session

T = TypeVar('T')


class BaseService(ABC):
    """Base class for domain services."""
    
    def __init__(self, db: Session):
        self.db = db
    
    @abstractmethod
    def create(self, data: dict[str, Any]) -> Any:
        """Create a new entity."""
        pass
    
    def get(self, id: int) -> Any | None:
        """Get an entity by ID."""
        return self.db.query(self._model).filter(self._model.id == id).first()
    
    def list(self, limit: int = 100) -> list[Any]:
        """List entities."""
        return self.db.query(self._model).limit(limit).all()
    
    def update(self, id: int, data: dict[str, Any]) -> Any:
        """Update an entity."""
        entity = self.get(id)
        if not entity:
            raise ValueError(f"Entity {id} not found")
        
        for key, value in data.items():
            setattr(entity, key, value)
        
        self.db.commit()
        self.db.refresh(entity)
        return entity
    
    def delete(self, id: int) -> bool:
        """Delete an entity."""
        entity = self.get(id)
        if not entity:
            return False
        
        self.db.delete(entity)
        self.db.commit()
        return True