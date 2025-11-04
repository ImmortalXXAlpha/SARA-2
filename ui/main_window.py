from PySide6.QtWidgets import (
    QWidget, QStackedWidget, QVBoxLayout, QPushButton, QHBoxLayout,
    QFrame, QSpacerItem, QSizePolicy, QComboBox
)
from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt
from ui.dashboard_page import DashboardPage
from ui.clean_tune_page import CleanTunePage
from ui.hardware_page import HardwarePage
from ui.ai_console_page import AIConsolePage
from ui.reports_page import ReportsPage
from ui.settings_page import SettingsPage


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SARA – AI Repair Agent")
        self.resize(1300, 750)

        # 🎨 Accent color options
        self.accents = {
            "Blue": "#6e8bff",
            "Purple": "#9b6eff",
            "Green": "#4ef57a",
            "Red": "#ff6e6e"
        }
        self.current_accent = self.accents["Blue"]

        # Initialize UI
        self.apply_theme(self.current_accent)
        self.build_ui()

    # 💡 Rebuilds style and re-applies with chosen accent
    def apply_theme(self, accent):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#0f1117"))
        palette.setColor(QPalette.WindowText, QColor("#e8eef6"))
        self.setPalette(palette)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: #0f1117;
                color: #e8eef6;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }}

            /* Sidebar styling */
            QFrame#sidebar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #141922, stop:1 #1e2635);
                border-right: 1px solid #2b3548;
            }}

            QPushButton {{
                background: #1b2230;
                color: #e8eef6;
                border: 1px solid #2b3548;
                border-radius: 10px;
                padding: 10px 14px;
                margin: 8px 14px;
                text-align: left;
                font-weight: 600;
                transition: all 0.2s ease-in-out;
            }}
            QPushButton:hover {{
                background: {accent};
                border-color: {accent};
                color: #fff;
                box-shadow: 0 0 12px {accent};
            }}
            QPushButton:pressed {{
                background: #1a2030;
                border-color: {accent};
            }}

            /* Titles & Subtitles */
            QLabel#title {{
                font-size: 28px;
                font-weight: 700;
                color: #ffffff;
                text-shadow: 0 0 8px rgba(255,255,255,0.25);
                margin-bottom: 4px;
            }}

            QLabel#subtitle {{
                color: #b4c2e2;
                font-size: 15px;
                font-weight: 500;
                margin-bottom: 12px;
            }}

            /* Cards and Frames */
            QFrame {{
                color: #e8eef6;
            }}

            /* Progress bars */
            QProgressBar {{
                background: #131a28;
                border: 1px solid #2b3548;
                border-radius: 8px;
                text-align: center;
                color: #e8eef6;
                min-height: 8px;
            }}
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 8px;
            }}

            /* ComboBox */
            QComboBox {{
                background: #1b2230;
                border: 1px solid #2b3548;
                border-radius: 6px;
                padding: 6px 10px;
                color: #e8eef6;
                font-weight: 500;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: #1b2230;
                border: 1px solid #2b3548;
                selection-background-color: {accent};
                selection-color: white;
            }}
        """)

    # ⚙️ Builds main window layout
    def build_ui(self):
        # Stacked pages
        self.stack = QStackedWidget()
        self.pages = {
            "Dashboard": DashboardPage(),
            "Clean Tune": CleanTunePage(),
            "Hardware": HardwarePage(),
            "AI Console": AIConsolePage(),
            "Reports": ReportsPage(),
            "Settings": SettingsPage()
        }
        for page in self.pages.values():
            page.setStyleSheet(self.styleSheet())
            self.stack.addWidget(page)

        # Sidebar (with spacing + accent switcher)
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setContentsMargins(8, 24, 8, 24)
        sidebar_layout.setSpacing(14)

        # Sidebar Buttons
        self.buttons = {}
        for name in self.pages.keys():
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, n=name: self.switch_page(n))
            sidebar_layout.addWidget(btn)
            self.buttons[name] = btn

        # Spacer and accent selector
        sidebar_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        accent_box = QComboBox()
        accent_box.addItems(self.accents.keys())
        accent_box.setCurrentText("Blue")
        accent_box.currentTextChanged.connect(self.change_accent)
        sidebar_layout.addWidget(accent_box)

        # Main layout: sidebar + stacked widget
        layout = QHBoxLayout(self)
        layout.addWidget(sidebar_frame, 1)
        layout.addWidget(self.stack, 5)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.switch_page("Dashboard")

    def switch_page(self, name):
        """Switch active content page and visually highlight sidebar button."""
        self.stack.setCurrentWidget(self.pages[name])
        accent = self.current_accent

        # Update button highlighting
        for n, btn in self.buttons.items():
            if n == name:
                btn.setStyleSheet(f"""
                    background: {accent};
                    color: white;
                    border-radius: 10px;
                    font-weight: 700;
                """)
            else:
                btn.setStyleSheet(f"""
                    background: #1b2230;
                    color: #e8eef6;
                    border: 1px solid #2b3548;
                    border-radius: 10px;
                    padding: 10px 14px;
                    text-align: left;
                    font-weight: 600;
                """)

    def change_accent(self, accent_name):
        """Change accent color dynamically."""
        self.current_accent = self.accents[accent_name]
        self.apply_theme(self.current_accent)
        # Re-apply style to all pages
        for page in self.pages.values():
            page.setStyleSheet(self.styleSheet())
        # Keep sidebar highlight consistent
        current_name = [k for k, v in self.pages.items() if v == self.stack.currentWidget()]
        if current_name:
            self.switch_page(current_name[0])
