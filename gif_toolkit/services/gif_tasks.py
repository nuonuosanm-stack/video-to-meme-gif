from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class GifTaskStore:
    def __init__(self, path: Path, *, now_ms=lambda: int(time.time() * 1000)) -> None:
        self.path = path
        self.now_ms = now_ms
        self._lock = threading.Lock()

    def _load_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def _save_unlocked(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, item: dict[str, Any]) -> dict[str, Any]:
        now = self.now_ms()
        record = {"created_at": now, "updated_at": now, **item}
        with self._lock:
            items = [record] + [task for task in self._load_unlocked() if task.get("task_id") != record.get("task_id")]
            self._save_unlocked(items[:500])
        return record

    def update(self, task_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            items = self._load_unlocked()
            updated = None
            for item in items:
                if str(item.get("task_id", "")) != str(task_id):
                    continue
                item.update(values)
                item["updated_at"] = self.now_ms()
                updated = item
                break
            if updated is not None:
                self._save_unlocked(items)
        return updated

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            for item in self._load_unlocked():
                if str(item.get("task_id", "")) == str(task_id):
                    return dict(item)
        return None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._load_unlocked()]

