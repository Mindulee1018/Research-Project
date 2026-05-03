import csv
import io
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app.model.moderation_models import (
    DecisionLogClearResult,
    DecisionLogCreateResult,
    DecisionLogExportResult,
    DecisionLogItem,
    DecisionLogListResult,
    DecisionLogRequest,
)
from app.model.response_models import GenericResponse


class DecisionLogService:
    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._lock = threading.Lock()
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def create(self, payload: DecisionLogRequest) -> GenericResponse[DecisionLogCreateResult]:
        item = DecisionLogItem(
            decision_id=str(uuid.uuid4()),
            item_id=payload.item_id.strip(),
            source=payload.source.strip(),
            text=payload.text,
            model_prediction=payload.model_prediction.strip().upper(),
            moderator_action=payload.moderator_action,
            final_label=payload.final_label,
            moderator_id=payload.moderator_id.strip() or "anonymous",
            notes=payload.notes,
            decided_at=payload.decided_at,
            logged_at=datetime.now(timezone.utc).isoformat(),
        )
        line = json.dumps(item.model_dump(), ensure_ascii=False)
        with self._lock:
            with self._log_path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(line + "\n")

        return GenericResponse[DecisionLogCreateResult].success_response(
            data=DecisionLogCreateResult(saved=True, decision=item),
            message="Decision logged.",
            status_code=201,
        )

    def list(self, limit: int = 100) -> GenericResponse[DecisionLogListResult]:
        items = self._read_all_items()
        clipped = items[-max(1, limit) :]
        return GenericResponse[DecisionLogListResult].success_response(
            data=DecisionLogListResult(total=len(items), items=clipped),
            message="Decision log list generated.",
            status_code=200,
        )

    def export(self, export_format: str = "json") -> GenericResponse[DecisionLogExportResult]:
        fmt = str(export_format).strip().lower()
        if fmt not in {"json", "csv"}:
            fmt = "json"
        items = self._read_all_items()

        if fmt == "csv":
            output = io.StringIO()
            fieldnames = list(DecisionLogItem.model_fields.keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow(item.model_dump())
            content = output.getvalue()
        else:
            content = json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2)

        return GenericResponse[DecisionLogExportResult].success_response(
            data=DecisionLogExportResult(format=fmt, total=len(items), content=content),
            message="Decision log export generated.",
            status_code=200,
        )

    def clear(self) -> GenericResponse[DecisionLogClearResult]:
        removed = len(self._read_all_items())
        with self._lock:
            if self._log_path.exists():
                self._log_path.write_text("", encoding="utf-8")
        return GenericResponse[DecisionLogClearResult].success_response(
            data=DecisionLogClearResult(cleared=True, removed=removed),
            message="Decision log cleared.",
            status_code=200,
        )

    def _read_all_items(self) -> List[DecisionLogItem]:
        if not self._log_path.exists():
            return []

        items: List[DecisionLogItem] = []
        with self._lock:
            with self._log_path.open("r", encoding="utf-8", newline="") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        items.append(DecisionLogItem(**payload))
                    except Exception:
                        continue
        return items
