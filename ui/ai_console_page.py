# ui/ai_console_page.py
"""
AI Console with thread-safe model switching.
Uses Qt signals for all cross-thread communication.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QFrame, QLineEdit, QComboBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot
from PySide6.QtGui import QTextCursor
import os
import json

# Try to import coordinator
try:
    from ai.ai_tool_coordinator import AIToolCoordinator
    HAS_COORDINATOR = True
except ImportError:
    HAS_COORDINATOR = False
    AIToolCoordinator = None


class AIWorker(QThread):
    """Background thread for AI generation."""
    response_ready = Signal(str)
    
    def __init__(self, ai, prompt, coordinator=None, max_new_tokens=256, temperature=0.7):
        super().__init__()
        self.ai = ai
        self.prompt = prompt
        self.coordinator = coordinator
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        if self._stopped:
            return
        
        # Safety checks
        if not self.ai:
            self.response_ready.emit("⚠️ AI backend not connected.")
            return
        if getattr(self.ai, 'is_loading', False):
            self.response_ready.emit("⚠️ Model is loading. Please wait...")
            return
        if not getattr(self.ai, 'is_loaded', False):
            self.response_ready.emit("⚠️ Model is not ready.")
            return
            
        # Check for tool commands first
        if self.coordinator and not self._stopped:
            try:
                tool_response, _ = self.coordinator.process_message(self.prompt)
                if tool_response:
                    self.response_ready.emit(tool_response)
                    return
            except:
                pass
        
        # AI generation
        if self._stopped:
            return
        
        try:
            result = self.ai.generate(
                self.prompt, 
                max_new_tokens=self.max_new_tokens, 
                temperature=self.temperature
            )
            if not self._stopped:
                self.response_ready.emit(result)
        except Exception as e:
            if not self._stopped:
                self.response_ready.emit(f"❌ Error: {e}")


class AIConsolePage(QWidget):
    # Signals for thread-safe UI updates from AI callbacks
    trigger_tool = Signal(str)
    _sig_progress = Signal(int)
    _sig_status = Signal(str)
    _sig_loaded = Signal()
    _sig_benchmark = Signal(float)
    _sig_vram = Signal(float, float)
    
    def __init__(self, ai=None, clean_tune_page=None):
        super().__init__()
        self.ai = ai
        self.clean_tune_page = clean_tune_page
        self.current_worker = None
        self.vram_timer = None
        
        # Settings
        self.settings_path = os.path.join(os.path.expanduser("~"), ".sara_settings.json")
        self.settings = self._load_settings()
        
        # Coordinator
        self.coordinator = None
        if HAS_COORDINATOR and AIToolCoordinator:
            try:
                self.coordinator = AIToolCoordinator(ai=ai, clean_tune_page=clean_tune_page)
                self.coordinator.tool_requested.connect(self._on_tool_requested)
            except:
                pass
        
        # Build UI
        self._init_ui()
        
        # Wire callbacks after a short delay
        QTimer.singleShot(100, self._wire_ai_callbacks)

    def set_clean_tune_page(self, page):
        self.clean_tune_page = page
        if self.coordinator:
            self.coordinator.set_clean_tune_page(page)

    def _load_settings(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("🤖 AI Console")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        # Model selector
        self.model_selector = QComboBox()
        if self.ai and hasattr(self.ai, 'MODELS'):
            keys = list(self.ai.MODELS.keys())
            self.model_selector.addItems(keys)
            current = getattr(self.ai, 'model_key', keys[0] if keys else '')
            if current in keys:
                self.model_selector.setCurrentIndex(keys.index(current))
            self.model_selector.currentTextChanged.connect(self._on_model_change)
        header.addWidget(QLabel("Model:"))
        header.addWidget(self.model_selector)

        self.status_label = QLabel("● Not Loaded")
        self.status_label.setStyleSheet("color:#FFA726; font-weight:600;")
        header.addWidget(self.status_label)
        layout.addLayout(header)

        # Info row
        info_row = QHBoxLayout()
        self.vram_label = QLabel("VRAM: -")
        self.benchmark_label = QLabel("Speed: -")
        info_row.addWidget(self.vram_label)
        info_row.addStretch()
        info_row.addWidget(self.benchmark_label)
        layout.addLayout(info_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        # Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            QTextEdit {
                background: #121826;
                border: 1px solid #2b3548;
                border-radius: 10px;
                padding: 12px;
                color: #e8eef6;
            }
        """)
        layout.addWidget(self.console, 1)

        # Input row
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask SARA...")
        self.input.returnPressed.connect(self.send_message)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_generation)
        self.stop_btn.setEnabled(False)
        
        input_row.addWidget(self.input, 5)
        input_row.addWidget(self.send_btn, 1)
        input_row.addWidget(self.stop_btn, 1)
        layout.addLayout(input_row)

        # Quick actions
        quick_row = QHBoxLayout()
        quick_row.addWidget(QLabel("Quick:"))
        for label, cmd in [("SFC", "run sfc"), ("DISM", "run dism"), ("Cleanup", "cleanup")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda c, x=cmd: self._quick_action(x))
            quick_row.addWidget(btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        self.setLayout(layout)
        
        # Welcome
        self._append_system("Welcome to SARA AI Console!")

    def _wire_ai_callbacks(self):
        """Connect AI callbacks via signals for thread safety."""
        if not self.ai:
            return
        
        # Connect signals to slots
        self._sig_progress.connect(self._slot_progress)
        self._sig_status.connect(self._slot_status)
        self._sig_loaded.connect(self._slot_loaded)
        self._sig_benchmark.connect(self._slot_benchmark)
        self._sig_vram.connect(self._slot_vram)
        
        # AI callbacks emit signals (safe from any thread)
        self.ai.on_progress = lambda v: self._sig_progress.emit(int(v))
        self.ai.on_status = lambda s: self._sig_status.emit(str(s))
        self.ai.on_loaded = lambda: self._sig_loaded.emit()
        self.ai.on_benchmark = lambda t: self._sig_benchmark.emit(float(t))
        self.ai.on_vram = lambda u, t: self._sig_vram.emit(float(u), float(t))

        # VRAM timer
        self.vram_timer = QTimer(self)
        self.vram_timer.timeout.connect(self._poll_vram)
        self.vram_timer.start(2000)
        
        # Auto-start load
        if not getattr(self.ai, 'is_loaded', False) and not getattr(self.ai, 'is_loading', False):
            QTimer.singleShot(200, self.ai.start_load)

    # ---- Thread-safe slots ----
    @Slot(int)
    def _slot_progress(self, v):
        try:
            self.progress.setValue(v)
            self.progress.setVisible(0 < v < 100)
        except:
            pass

    @Slot(str)
    def _slot_status(self, s):
        try:
            self.status_label.setText(s)
        except:
            pass

    @Slot()
    def _slot_loaded(self):
        try:
            self._set_loading_state(False)
            self.status_label.setText("● Ready")
            self.status_label.setStyleSheet("color:#4CAF50; font-weight:600;")
            self.progress.hide()
            model = getattr(self.ai, 'model_key', 'unknown')
            self._append_system(f"✅ Model {model} ready!")
        except:
            pass

    @Slot(float)
    def _slot_benchmark(self, tps):
        try:
            self.benchmark_label.setText(f"Speed: {tps} t/s")
        except:
            pass

    @Slot(float, float)
    def _slot_vram(self, used, total):
        try:
            if total > 0:
                self.vram_label.setText(f"VRAM: {used:.1f}/{total:.1f} GB")
            else:
                self.vram_label.setText("VRAM: CPU")
        except:
            pass

    def _poll_vram(self):
        if self.ai and hasattr(self.ai, 'get_vram_usage_gb'):
            try:
                u, t = self.ai.get_vram_usage_gb()
                self._slot_vram(u, t)
            except:
                pass

    # ---- Messages ----
    def _append_user(self, text):
        self.console.append(f'<p style="color:#6e8bff;"><b>You:</b> {text}</p>')
        self._scroll_bottom()

    def _append_ai(self, text):
        text = str(text).replace("\n", "<br>")
        self.console.append(f'<p style="color:#e8eef6;"><b>🤖 SARA:</b> {text}</p>')
        self._scroll_bottom()

    def _append_system(self, text):
        self.console.append(f'<p style="color:#9eb3ff;"><i>{text}</i></p>')
        self._scroll_bottom()

    def _scroll_bottom(self):
        try:
            c = self.console.textCursor()
            c.movePosition(QTextCursor.End)
            self.console.setTextCursor(c)
        except:
            pass

    def _quick_action(self, cmd):
        self.input.setText(cmd)
        self.send_message()

    # ---- Send message ----
    def send_message(self):
        if not self.ai:
            self._append_ai("⚠️ AI not connected.")
            return
        if getattr(self.ai, 'is_loading', False):
            self._append_ai("⚠️ Model loading...")
            return
        if not getattr(self.ai, 'is_loaded', False):
            self._append_ai("⚠️ Model not ready.")
            return
            
        text = self.input.text().strip()
        if not text:
            return
            
        self._append_user(text)
        self.input.clear()
        self._set_generating(True)

        max_tok = int(self.settings.get("max_tokens", 256))
        temp = float(self.settings.get("temperature", 0.7))
        
        self.current_worker = AIWorker(self.ai, text, self.coordinator, max_tok, temp)
        self.current_worker.response_ready.connect(self._on_response)
        self.current_worker.start()

    @Slot(str)
    def _on_response(self, resp):
        self._append_ai(resp)
        self._set_generating(False)

    def stop_generation(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.stop()
        self._set_generating(False)

    def _set_generating(self, active):
        self.input.setEnabled(not active)
        self.send_btn.setEnabled(not active)
        self.stop_btn.setEnabled(active)

    # ---- Model switch ----
    def _on_model_change(self, key):
        if not self.ai:
            return
        if getattr(self.ai, 'is_loading', False):
            self._append_system("⏳ Already loading...")
            self._reset_selector()
            return
        if key == getattr(self.ai, 'model_key', '') and getattr(self.ai, 'is_loaded', False):
            return
        
        self._set_loading_state(True)
        self._append_system(f"🔄 Switching to {key}...")
        
        # Delay the switch to let UI update first
        QTimer.singleShot(50, lambda: self._do_switch(key))

    def _do_switch(self, key):
        try:
            if self.ai:
                self.ai.switch_model(key)
        except Exception as e:
            self._append_system(f"❌ Error: {e}")
            self._set_loading_state(False)

    def _reset_selector(self):
        try:
            if self.ai and hasattr(self.ai, 'model_key'):
                keys = list(self.ai.MODELS.keys())
                if self.ai.model_key in keys:
                    self.model_selector.blockSignals(True)
                    self.model_selector.setCurrentIndex(keys.index(self.ai.model_key))
                    self.model_selector.blockSignals(False)
        except:
            pass

    def _set_loading_state(self, loading):
        self.input.setEnabled(not loading)
        self.send_btn.setEnabled(not loading)
        self.model_selector.setEnabled(not loading)
        if loading:
            self.progress.show()
            self.progress.setValue(10)
            self.status_label.setText("● Loading...")
            self.status_label.setStyleSheet("color:#FFA726; font-weight:600;")

    @Slot(str, dict)
    def _on_tool_requested(self, tool_name, options):
        if self.clean_tune_page and hasattr(self.clean_tune_page, '_start_tool'):
            QTimer.singleShot(0, lambda: self.clean_tune_page._start_tool(tool_name))