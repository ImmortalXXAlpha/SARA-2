import os
from pathlib import Path
import datetime
import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QHBoxLayout
)

# Points to the same reports directory used in clean_tune_page.py
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


class ReportsPage(QWidget):
    """
    Displays all generated system logs and allows the user
    to open them directly in their default text viewer.
    """
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        title = QLabel("📜 System Reports")
        title.setObjectName("title")

        subtitle = QLabel("View detailed logs from system maintenance tools")
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # List of saved logs
        self.list = QListWidget()
        self.list.setStyleSheet("""
            QListWidget {
                background-color: #121826;
                border: 1px solid #2b3548;
                border-radius: 8px;
                color: #e8eef6;
                font-size: 13px;
                padding: 6px;
            }
            QListWidget::item:selected {
                background: #6e8bff;
                color: white;
            }
        """)
        layout.addWidget(self.list)

        # Refresh and open buttons
        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_open = QPushButton("📂 Open Selected")

        for b in (self.btn_refresh, self.btn_open):
            b.setStyleSheet("""
                QPushButton {
                    background: #6e8bff;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px;
                    font-weight: 600;
                }
                QPushButton:hover { background: #869eff; }
            """)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_open.clicked.connect(self.open_selected)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_open)
        layout.addLayout(btn_row)

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(10000)  # auto-refresh every 10s

        self.refresh()

    # ───────────────────────────────
    # List/Refresh
    # ───────────────────────────────
    def refresh(self):
        """Reloads the list of report files."""
        self.list.clear()
        if not REPORTS_DIR.exists():
            REPORTS_DIR.mkdir(exist_ok=True)

        files = sorted(REPORTS_DIR.glob("*.txt"), key=os.path.getmtime, reverse=True)
        if not files:
            item = QListWidgetItem("No reports found yet.")
            item.setFlags(Qt.NoItemFlags)
            self.list.addItem(item)
            return

        for f in files:
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            label = f"{f.name}  ({mtime.strftime('%Y-%m-%d %H:%M:%S')})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(f))
            self.list.addItem(item)

    # ───────────────────────────────
    # Open selected report
    # ───────────────────────────────
    def open_selected(self):
        """Opens the selected file in Notepad or default text viewer."""
        item = self.list.currentItem()
        if not item or not item.data(Qt.UserRole):
            QMessageBox.information(self, "Open Report", "Please select a report to open.")
            return
        path = item.data(Qt.UserRole)
        if not os.path.exists(path):
            QMessageBox.warning(self, "Missing File", "That report no longer exists.")
            return

        try:
            webbrowser.open(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")
