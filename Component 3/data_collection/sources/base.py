from abc import ABC, abstractmethod
from typing import Dict, List

from data_collection.models import SourceRecord


class SourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def load(self, config: Dict[str, str]) -> List[SourceRecord]:
        """Load source records from adapter-specific input."""

