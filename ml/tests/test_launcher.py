"""Unit tests for LauncherWindow (anti_uav/gui/launcher.py).

Uses QApplication directly since pytest-qt may not be installed.
"""
from __future__ import annotations

import sys

import pytest

pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QApplication, QPushButton, QComboBox  # noqa: E402

from anti_uav.gui.launcher import LauncherWindow  # noqa: E402

TAB_NAMES = [
    "Inspector",
    "Reviewer",
    "Normalizer",
    "Backend",
    "Merger",
    "Trainer",
    "Documenter",
    "Comparator",
    "Colab Bridge",
    "Manual",
]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_launcher_window_opens(qapp):
    """LauncherWindow should instantiate without error."""
    win = LauncherWindow()
    assert win is not None
    win.close()


def test_launcher_has_all_tabs(qapp):
    """Tab widget must have exactly 10 tabs with the correct names."""
    win = LauncherWindow()
    tabs = win._tabs
    assert tabs.count() == 10
    for i, name in enumerate(TAB_NAMES):
        assert tabs.tabText(i) == name
    win.close()


def test_launcher_inspector_tab_has_button(qapp):
    """Inspector tab must contain a 'Run Inspector' QPushButton."""
    win = LauncherWindow()
    inspector_widget = win._tabs.widget(0)
    buttons = inspector_widget.findChildren(QPushButton)
    labels = [b.text() for b in buttons]
    assert "Run Inspector" in labels
    win.close()


def test_launcher_trainer_tab_has_profile_combo(qapp):
    """Trainer tab must contain a hardware profile QComboBox."""
    win = LauncherWindow()
    trainer_widget = win._tabs.widget(5)
    combos = trainer_widget.findChildren(QComboBox)
    assert len(combos) >= 1
    items = [combos[0].itemText(i) for i in range(combos[0].count())]
    assert "rtx2070" in items
    win.close()


def test_launcher_colab_tab_has_backend_combo(qapp):
    """Colab Bridge tab must contain a backend QComboBox with Colab/Kaggle options."""
    win = LauncherWindow()
    colab_widget = win._tabs.widget(8)
    combos = colab_widget.findChildren(QComboBox)
    assert len(combos) >= 1
    items = [combos[0].itemText(i) for i in range(combos[0].count())]
    assert "Colab" in items
    assert "Kaggle" in items
    win.close()
