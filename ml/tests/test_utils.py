"""Unit tests for anti_uav/utils.py"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from anti_uav.utils import atomic_write, configure_logging, get_logger, sha256_hash


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------

def test_get_logger_returns_logger_under_anti_uav_namespace():
    logger = get_logger("inspector")
    assert logger.name == "anti_uav.inspector"


def test_get_logger_adds_stream_handler_to_root():
    root = logging.getLogger("anti_uav")
    # Clear handlers so we can test fresh addition
    root.handlers.clear()
    get_logger("test_add_handler")
    assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)


def test_get_logger_does_not_add_duplicate_handlers():
    root = logging.getLogger("anti_uav")
    root.handlers.clear()
    get_logger("dup1")
    get_logger("dup2")
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
    assert len(stream_handlers) == 1


def test_get_logger_format_has_no_asctime(caplog):
    root = logging.getLogger("anti_uav")
    root.handlers.clear()
    logger = get_logger("fmt_check")
    handler = root.handlers[0]
    fmt = handler.formatter._fmt
    assert "asctime" not in fmt
    assert "%(levelname)s" in fmt
    assert "%(name)s" in fmt


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------

def test_configure_logging_verbose_sets_debug():
    configure_logging(verbose=True)
    assert logging.getLogger("anti_uav").level == logging.DEBUG


def test_configure_logging_non_verbose_sets_info():
    configure_logging(verbose=False)
    assert logging.getLogger("anti_uav").level == logging.INFO


def test_configure_logging_is_idempotent():
    root = logging.getLogger("anti_uav")
    root.handlers.clear()
    get_logger("idempotent_seed")  # ensure one handler exists
    handler_count_before = len(root.handlers)
    configure_logging(verbose=True)
    configure_logging(verbose=True)
    assert len(root.handlers) == handler_count_before


# ---------------------------------------------------------------------------
# atomic_write
# ---------------------------------------------------------------------------

def test_atomic_write_creates_file(tmp_path):
    target = tmp_path / "output.json"
    atomic_write(target, '{"key": "value"}')
    assert target.exists()
    assert target.read_text() == '{"key": "value"}'


def test_atomic_write_no_tmp_file_left(tmp_path):
    target = tmp_path / "output.txt"
    atomic_write(target, "hello")
    tmp = target.with_suffix(target.suffix + ".tmp")
    assert not tmp.exists()


def test_atomic_write_creates_parent_dirs(tmp_path):
    target = tmp_path / "a" / "b" / "c" / "file.txt"
    atomic_write(target, "nested")
    assert target.exists()
    assert target.read_text() == "nested"


def test_atomic_write_overwrites_existing(tmp_path):
    target = tmp_path / "file.txt"
    atomic_write(target, "first")
    atomic_write(target, "second")
    assert target.read_text() == "second"


# ---------------------------------------------------------------------------
# sha256_hash
# ---------------------------------------------------------------------------

def test_sha256_hash_known_value(tmp_path):
    import hashlib
    content = b"anti-uav test content"
    f = tmp_path / "test.bin"
    f.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert sha256_hash(f) == expected


def test_sha256_hash_empty_file(tmp_path):
    import hashlib
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    expected = hashlib.sha256(b"").hexdigest()
    assert sha256_hash(f) == expected


def test_sha256_hash_different_files_differ(tmp_path):
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"aaa")
    f2.write_bytes(b"bbb")
    assert sha256_hash(f1) != sha256_hash(f2)


def test_sha256_hash_identical_content_matches(tmp_path):
    f1 = tmp_path / "x.bin"
    f2 = tmp_path / "y.bin"
    data = b"same content"
    f1.write_bytes(data)
    f2.write_bytes(data)
    assert sha256_hash(f1) == sha256_hash(f2)
