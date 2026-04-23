from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home


CRON_DIR = get_hermes_home().resolve() / "cron"
RECEIPTS_FILE = CRON_DIR / "dispatch_receipts.json"

_receipts_file_lock = threading.Lock()


def _secure_dir(path: Path) -> None:
    try:
        os.chmod(path, 0o700)
    except (OSError, NotImplementedError):
        pass


def _secure_file(path: Path) -> None:
    try:
        if path.exists():
            os.chmod(path, 0o600)
    except (OSError, NotImplementedError):
        pass


def ensure_receipts_dir() -> None:
    CRON_DIR.mkdir(parents=True, exist_ok=True)
    _secure_dir(CRON_DIR)


def _load_receipts_unlocked() -> dict[str, dict[str, Any]]:
    ensure_receipts_dir()
    if not RECEIPTS_FILE.exists():
        return {}
    with open(RECEIPTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("receipts", {})
    if not isinstance(raw, dict):
        return {}
    return {str(key): value for key, value in raw.items() if isinstance(value, dict)}


def _save_receipts_unlocked(receipts: dict[str, dict[str, Any]]) -> None:
    ensure_receipts_dir()
    fd, tmp_path = tempfile.mkstemp(dir=str(RECEIPTS_FILE.parent), suffix=".tmp", prefix=".dispatch_receipts_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"receipts": receipts}, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, RECEIPTS_FILE)
        _secure_file(RECEIPTS_FILE)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_receipt(occurrence_id: str) -> dict[str, Any] | None:
    with _receipts_file_lock:
        return _load_receipts_unlocked().get(occurrence_id)


def create_receipt_if_absent(receipt: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    occurrence_id = str(receipt.get("occurrence_id") or "").strip()
    if not occurrence_id:
        raise ValueError("Receipt must include occurrence_id.")
    with _receipts_file_lock:
        receipts = _load_receipts_unlocked()
        existing = receipts.get(occurrence_id)
        if existing is not None:
            return existing, False
        receipts[occurrence_id] = dict(receipt)
        _save_receipts_unlocked(receipts)
        return receipts[occurrence_id], True


def update_receipt(occurrence_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    with _receipts_file_lock:
        receipts = _load_receipts_unlocked()
        existing = receipts.get(occurrence_id)
        if existing is None:
            raise KeyError(occurrence_id)
        receipts[occurrence_id] = {**existing, **updates}
        _save_receipts_unlocked(receipts)
        return receipts[occurrence_id]
