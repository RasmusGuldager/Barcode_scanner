"""Daily backups: a dated export file, keeping only the newest ones."""

import json
from datetime import UTC, datetime
from pathlib import Path

from .transfer import export_data

KEEP = 30
PREFIX = "rental-"


def backup_files(directory: Path) -> list[Path]:
    """Backups in ``directory``, newest first."""
    return sorted(directory.glob(f"{PREFIX}*.json"), reverse=True)


def write_backup(directory: Path, keep: int = KEEP) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
    path = directory / f"{PREFIX}{stamp}.json"
    path.write_text(json.dumps(export_data(), indent=2, ensure_ascii=False))
    for old in backup_files(directory)[keep:]:
        old.unlink()
    return path
