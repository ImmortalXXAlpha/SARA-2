from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout, QFrame, QLineEdit

class AIConsolePage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("🤖 AI Console")
        title.setObjectName("title")
        subtitle = QLabel("Ask SARA AI for help with diagnostics and system insights")
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Console output area
        console_frame = QFrame()
        console_frame.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
            }
        """)
        console_layout = QVBoxLayout(console_frame)
        self.console = QTextEdit()
        self.console.setPlaceholderText("AI responses will appear here...")
        self.console.setStyleSheet("""
            QTextEdit {
                background: #0f1522;
                color: #e8eef6;
                border-radius: 8px;
                border: 1px solid #2b3548;
            }
        """)
        console_layout.addWidget(self.console)
        layout.addWidget(console_frame, 1)

        # Input bar
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a question for SARA...")
        self.input.setStyleSheet("""
            QLineEdit {
                background: #0f1522;
                color: #e8eef6;
                border: 1px solid #2b3548;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        send_btn = QPushButton("Send")
        send_btn.setStyleSheet("""
            QPushButton {
                background: #6e8bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background: #869eff; }
        """)
        input_row.addWidget(self.input, 5)
        input_row.addWidget(send_btn, 1)
        layout.addLayout(input_row)
        self.setLayout(layout)
