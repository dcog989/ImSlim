from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from imslim.formats import Format
from imslim.settings_manager import (
    COMPRESSION_TIMEOUT_MAX,
    COMPRESSION_TIMEOUT_MIN,
    SAVE_NEXT_TO_ORIGINAL,
    SAVE_OUTPUT_FOLDER,
    SettingsManager,
)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point QSettings at a throwaway file so tests never touch the real config."""
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))

    class _ScopedSettings(QSettings):
        # The 2-argument constructor ignores setPath; force the scope and format.
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__(
                QSettings.Format.IniFormat, QSettings.Scope.UserScope, "ImSlim", "ImSlim"
            )

    monkeypatch.setattr("imslim.settings_manager.QSettings", _ScopedSettings)
    assert _ScopedSettings().fileName().startswith(str(tmp_path))


def _store() -> QSettings:
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "ImSlim", "ImSlim")


def test_unknown_target_format_falls_back_to_keep() -> None:
    store = _store()
    store.setValue("target-format", "jpg")
    store.sync()

    assert SettingsManager().target_format is Format.KEEP


def test_blank_target_format_falls_back_to_keep() -> None:
    store = _store()
    store.setValue("target-format", "")
    store.sync()

    assert SettingsManager().target_format is Format.KEEP


def test_migration_moves_an_old_output_folder_to_its_own_destination() -> None:
    store = _store()
    store.setValue("save-method", SAVE_NEXT_TO_ORIGINAL)
    store.setValue("output-folder", "/tmp/old-output")
    store.sync()

    assert SettingsManager().save_method == SAVE_OUTPUT_FOLDER


def test_migration_runs_only_once() -> None:
    store = _store()
    store.setValue("save-method", SAVE_NEXT_TO_ORIGINAL)
    store.setValue("output-folder", "/tmp/old-output")
    store.sync()
    manager = SettingsManager()
    manager.save_method = SAVE_NEXT_TO_ORIGINAL
    manager.sync()

    assert SettingsManager().save_method == SAVE_NEXT_TO_ORIGINAL


def test_timeout_from_the_config_file_is_clamped() -> None:
    store = _store()
    store.setValue("compression-timeout", 0)
    store.sync()
    assert SettingsManager().compression_timeout == COMPRESSION_TIMEOUT_MIN

    store.setValue("compression-timeout", 9999)
    store.sync()
    assert SettingsManager().compression_timeout == COMPRESSION_TIMEOUT_MAX


def test_unrecognised_boolean_falls_back_to_the_default() -> None:
    store = _store()
    store.setValue("metadata", "banana")
    store.sync()

    assert SettingsManager().metadata is True


def test_boolean_settings_round_trip() -> None:
    manager = SettingsManager()
    manager.metadata = False

    assert manager.metadata is False
    assert SettingsManager().metadata is False
