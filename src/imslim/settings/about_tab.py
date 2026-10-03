from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import __version__
from .._i18n import _
from ..icons import imslim_icon
from ..settings_manager import log_file_path
from ..system_info import static_about_pairs, system_info_pairs
from ..workers import VersionProbeTask, start_task


class AboutTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool_pairs: list[tuple[str, str]] = []
        self._populated = False
        self._probe_worker: VersionProbeTask | None = None
        self._env_label: QLabel = QLabel()
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        icon = QLabel()
        icon.setPixmap(imslim_icon().pixmap(64))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        message = QLabel()
        message.setTextFormat(Qt.TextFormat.RichText)
        message.setOpenExternalLinks(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setText(
            _(
                "<div style='font-size: 18pt; font-weight: bold;'>ImSlim</div>"
                + "<div style='font-size: 9pt; color: #808080;'>Version {version}</div>"
                + "<div style='margin-top: 10px;'>"
                + "Compress common image formats, lossless or lossy.</div>"
                + "<div style='margin-top: 8px;'>"
                + "<a href='{log_url}'>Open latest log file</a> · "
                + "<a href='https://github.com/dcog989/ImSlim'>GitHub</a></div>"
            ).format(version=__version__, log_url=QUrl.fromLocalFile(log_file_path()).toString())
        )
        layout.addWidget(message)

        self._env_label.setWordWrap(True)
        self._env_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._env_label)

        copy_button = QPushButton(_("Copy Environment"))
        copy_button.setFixedWidth(160)
        copy_button.clicked.connect(self._copy_environment)
        layout.addWidget(copy_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

    def populate(self) -> None:
        if self._populated:
            return
        self._populated = True
        # System/static info is cheap and synchronous; tool versions spawn
        # subprocesses, so probe them off the UI thread.
        self._env_label.setText(self._env_text())
        worker = VersionProbeTask()
        worker.versions_ready.connect(self._on_versions)
        self._probe_worker = worker
        start_task(worker)

    def _env_text(self) -> str:
        lines: list[str] = []
        lines += [f"{key}: {value}" for key, value in static_about_pairs()]
        lines += [f"{key}: {value}" for key, value in system_info_pairs()]
        qt_platform = QApplication.platformName()
        if qt_platform:
            lines.append(f"Qt Platform: {qt_platform}")
        lines += [f"{key}: {value}" for key, value in self._tool_pairs]
        return "\n".join(lines)

    def _on_versions(self, tool_pairs: list[tuple[str, str]]) -> None:
        self._tool_pairs = tool_pairs
        self._env_label.setText(self._env_text())

    def _copy_environment(self) -> None:
        QApplication.clipboard().setText(self._env_text())
