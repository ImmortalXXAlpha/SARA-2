from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QHBoxLayout, QFrame, QLineEdit, QComboBox, QScrollArea, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ai.local_ai import LocalAI
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("⚠️ Local AI backend not available.")


class AIWorker(QThread):
    """Background thread for AI generation"""
    response_ready = Signal(str)
    
    def __init__(self, ai_backend, prompt):
        super().__init__()
        self.ai_backend = ai_backend
        self.prompt = prompt
    
    def run(self):
        response = self.ai_backend.generate(self.prompt)
        self.response_ready.emit(response)


class ModelLoaderThread(QThread):
    """Thread to load local model with progress callback"""
    progress_update = Signal(int)
    model_loaded = Signal()

    def __init__(self, ai_backend):
        super().__init__()
        self.ai_backend = ai_backend

    def run(self):
        """Load tokenizer, model, and finish setup, reporting progress"""
        try:
            self.progress_update.emit(10)
            # Load tokenizer
            self.ai_backend.tokenizer = self.ai_backend.tokenizer or self.ai_backend._load_tokenizer()
            self.progress_update.emit(40)

            # Load model
            self.ai_backend.model = self.ai_backend.model or self.ai_backend._load_model()
            self.progress_update.emit(80)

            # Post-setup (device map, etc.)
            self.ai_backend.is_loaded = True
            self.ai_backend.is_loading = False
            self.progress_update.emit(100)
            self.model_loaded.emit()
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            self.ai_backend.is_loading = False


class AIConsolePage(QWidget):
    def __init__(self):
        super().__init__()
        self.ai_backend = LocalAI() if AI_AVAILABLE else None
        self.current_worker = None
        self.model_loader = None
        self.setup_ui()
        if self.ai_backend:
            self.start_model_loading()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("🤖 AI Console (Local)")
        title.setObjectName("title")
        
        model_label = QLabel("Model:")
        self.model_selector = QComboBox()
        if self.ai_backend:
            self.model_selector.addItem(self.ai_backend.model_name)
            self.model_selector.currentTextChanged.connect(self.change_model)
        
        self.status_label = QLabel("● Loading..." if self.ai_backend else "● Not Connected")
        self.status_label.setStyleSheet("color: #FFA726; font-weight: 600;")
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(model_label)
        header_layout.addWidget(self.model_selector)
        header_layout.addWidget(self.status_label)
        layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Subtitle
        subtitle = QLabel("Ask SARA AI for help with system diagnostics and insights")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        # Console output area
        console_scroll = QScrollArea()
        console_scroll.setWidgetResizable(True)
        console_scroll.setStyleSheet("""
            QScrollArea { border: 1px solid #2b3548; border-radius: 12px; }
        """)
        self.console_content = QWidget()
        self.console_layout = QVBoxLayout(self.console_content)
        self.console_layout.setAlignment(Qt.AlignTop)
        self.console_layout.setSpacing(15)
        console_scroll.setWidget(self.console_content)
        layout.addWidget(console_scroll, 1)

        # Input bar
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a question for SARA...")
        self.input.returnPressed.connect(self.send_message)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send_message)
        self.send_btn = send_btn
        input_row.addWidget(self.input, 5)
        input_row.addWidget(send_btn, 1)
        layout.addLayout(input_row)

        self.setLayout(layout)

        # Welcome message
        self.add_ai_message(
            "Hello! I'm SARA, your local AI assistant.\n"
            "I can help with:\n• System diagnostics\n• Performance troubleshooting\n"
            "• Error analysis\n• Optimization recommendations\n\n"
            "What can I help you with today?"
        )

    def start_model_loading(self):
        """Start model loading in background thread"""
        self.model_loader = ModelLoaderThread(self.ai_backend)
        self.model_loader.progress_update.connect(self.update_progress)
        self.model_loader.model_loaded.connect(self.model_ready)
        self.model_loader.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def model_ready(self):
        self.status_label.setText("● Ready")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: 600;")
        self.progress_bar.hide()

    def add_user_message(self, text):
        msg_frame = QFrame()
        msg_frame.setStyleSheet("background: #6e8bff; border-radius: 12px; padding: 12px;")
        layout = QVBoxLayout(msg_frame)
        label = QLabel(text)
        label.setStyleSheet("color: white; font-size: 14px;")
        label.setWordWrap(True)
        layout.addWidget(label)
        container = QHBoxLayout()
        container.addStretch()
        container.addWidget(msg_frame, stretch=3)
        widget = QWidget()
        widget.setLayout(container)
        self.console_layout.addWidget(widget)

    def add_ai_message(self, text):
        msg_frame = QFrame()
        msg_frame.setStyleSheet("border: 1px solid #2b3548; border-radius: 12px; padding: 12px;")
        layout = QVBoxLayout(msg_frame)
        label = QLabel(text)
        label.setStyleSheet("font-size: 14px;")
        label.setWordWrap(True)
        layout.addWidget(label)
        container = QHBoxLayout()
        container.addWidget(msg_frame, stretch=3)
        container.addStretch()
        widget = QWidget()
        widget.setLayout(container)
        self.console_layout.addWidget(widget)

    def send_message(self):
        if not self.ai_backend or not self.ai_backend.is_loaded:
            self.add_ai_message("⚠️ Model is still loading...")
            return
        text = self.input.text().strip()
        if not text:
            return
        self.add_user_message(text)
        self.input.clear()
        self.input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.status_label.setText("● Processing...")
        self.status_label.setStyleSheet("color: #FFA726; font-weight: 600;")
        self.current_worker = AIWorker(self.ai_backend, text)
        self.current_worker.response_ready.connect(self.handle_response)
        self.current_worker.start()

    def handle_response(self, response):
        self.add_ai_message(response)
        self.input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.status_label.setText("● Ready")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: 600;")
        scroll_bar = self.console_content.parent().parent().verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def change_model(self, model_name):
        if self.ai_backend:
            self.ai_backend.switch_model(model_name)
            self.add_ai_message(f"🔄 Switched to {model_name}")
