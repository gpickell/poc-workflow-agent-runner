"""Append-only JSONL transcript of one session: commands, every SDK event, and what Clara saw."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

FOLDER = Path.home() / ".workflow-agent-runner" / "transcripts"


class Transcript:
    def __init__(self) -> None:
        FOLDER.mkdir(parents=True, exist_ok=True)
        self.path = FOLDER / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl"
        self._file: TextIO | None = None  # opened on first write, so unused sessions leave no file

    def write(self, event: str, **data: Any) -> None:
        if self._file is None:
            self._file = self.path.open("a", encoding="utf-8")
        entry = {"t": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event, **data}
        self._file.write(json.dumps(entry, default=str) + "\n")
        self._file.flush()

    def sdk(self, message: object) -> None:
        """Record an SDK message as {"type": class name, ...fields}."""
        fields = dataclasses.asdict(message) if dataclasses.is_dataclass(message) else {"repr": repr(message)}
        self.write("sdk", message={"type": type(message).__name__, **fields})

    def close(self) -> None:
        if self._file:
            self._file.close()
