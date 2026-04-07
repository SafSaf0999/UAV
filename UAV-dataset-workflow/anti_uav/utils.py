from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the anti_uav namespace, adding a StreamHandler if none configured."""
    logger = logging.getLogger(f"anti_uav.{name}")
    root = logging.getLogger("anti_uav")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)
    return logger


def configure_logging(verbose: bool) -> None:
    """Set the anti_uav root logger level to DEBUG (verbose) or INFO."""
    logging.getLogger("anti_uav").setLevel(logging.DEBUG if verbose else logging.INFO)


def atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via a .tmp file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def sha256_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of the file at path, read in 64 KiB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
