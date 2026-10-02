from __future__ import annotations

import json
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


Status = Literal["uploaded", "processing", "complete", "failed"]


@dataclass
class Job:
    id: str
    media_type: Literal["image", "video"]
    filename: str
    source_name: str
    result_name: str
    width: int
    height: int
    duration: float | None
    status: Status = "uploaded"
    progress: float = 0
    error: str | None = None
    created_at: float = 0


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._load()

    def _load(self) -> None:
        for metadata in self.root.glob("*/job.json"):
            try:
                data = json.loads(metadata.read_text(encoding="utf-8"))
                job = Job(**data)
                if job.status == "processing":
                    job.status = "failed"
                    job.error = "Processing was interrupted when the server stopped."
                self._jobs[job.id] = job
                self.save(job)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue

    def directory(self, job_id: str) -> Path:
        return self.root / job_id

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job
            self.save(job)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def save(self, job: Job) -> None:
        with self._lock:
            directory = self.directory(job.id)
            directory.mkdir(parents=True, exist_ok=True)
            metadata = directory / "job.json"
            temporary = directory / "job.json.tmp"
            temporary.write_text(json.dumps(asdict(job), indent=2), encoding="utf-8")
            temporary.replace(metadata)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            existed = self._jobs.pop(job_id, None) is not None
            directory = self.directory(job_id)
            if directory.exists():
                shutil.rmtree(directory)
                existed = True
            return existed

    def cleanup(self, ttl_hours: int) -> int:
        cutoff = time.time() - ttl_hours * 3600
        expired = []
        with self._lock:
            for job_id, job in self._jobs.items():
                if job.created_at < cutoff and job.status != "processing":
                    expired.append(job_id)
        for job_id in expired:
            self.delete(job_id)
        return len(expired)

