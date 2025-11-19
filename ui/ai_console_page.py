# ui/ai_console_page.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QFrame, QLineEdit, QComboBox, QScrollArea, QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
import os, json

# We'll accept a shared NovaAI instance from MainWindow
class AIWorker(QThread):
    response_ready = Signal(str)
    def __init__(self, ai, prompt, max_new_tokens=256, temperature=0.7):
        super().__init__()
        self.ai = ai
        self.prompt = prompt
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        # synchronous generate — run in a worker thread
        result = self.ai.generate(self.prompt, max_new_tokens=self.max_new_tokens, temperature=self.temperature)
        self.response_ready.emit(result)

class AIConsolePage(QWidget):
    def __init__(self, ai=None):
        super().__init__()
        self.ai = ai  # shared NovaAI
        self.current_worker = None
        self.model_loader = None
        self.settings_path = os.path.join(os.path.expanduser("~"), ".sara_settings.json")
        self.settings = self._load_settings()
        self._init_ui()
        if self.ai:
            self._wire_ai_callbacks()
            # auto start load if not loaded
            if not self.ai.is_loaded and not self.ai.is_loading:
                self.ai.start_load()

    def _load_settings(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("🤖 AI Console (Local)")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        # Model selector uses available keys if ai present
        self.model_selector = QComboBox()
        if self.ai:
            keys = list(self.ai.MODELS.keys())
            self.model_selector.addItems(keys)
            idx = keys.index(self.ai.model_key) if self.ai.model_key in keys else 0
            self.model_selector.setCurrentIndex(idx)
            self.model_selector.currentTextChanged.connect(self._on_model_change)
        header.addWidget(QLabel("Model:"))
        header.addWidget(self.model_selector)

        self.status_label = QLabel("● Ready" if self.ai and self.ai.is_loaded else "● Not Loaded")
        self.status_label.setStyleSheet("color:#FFA726; font-weight:600;")
        header.addWidget(self.status_label)
        layout.addLayout(header)

        # VRAM / benchmark row
        info_row = QHBoxLayout()
        self.vram_label = QLabel("VRAM: - / -")
        self.benchmark_label = QLabel("Speed: - t/s")
        info_row.addWidget(self.vram_label)
        info_row.addStretch()
        info_row.addWidget(self.benchmark_label)
        layout.addLayout(info_row)

        # progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # console area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.console_content = QWidget()
        self.console_layout = QVBoxLayout(self.console_content)
        self.console_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.console_content)
        layout.addWidget(scroll, 1)

        # input row
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask SARA about logs, errors, or hardware...")
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

        # footer small status
        footer = QHBoxLayout()
        self.footer_status = QLabel("")
        self.footer_vram = QLabel("")
        footer.addWidget(self.footer_status)
        footer.addStretch()
        footer.addWidget(self.footer_vram)
        layout.addLayout(footer)

        self.setLayout(layout)

    # ----------------- wiring & callbacks -----------------
    def _wire_ai_callbacks(self):
        # connect nova-ai callbacks to UI update methods
        self.ai.on_progress = lambda v: self.progress.setValue(v)
        self.ai.on_status = lambda s: self._set_status(s)
        self.ai.on_loaded = lambda: self._on_model_ready()
        self.ai.on_benchmark = lambda t: self._on_benchmark(t)
        self.ai.on_vram = lambda used, total: self._on_vram(used, total)

        # start periodic poll for VRAM (redundant if ai calls back)
        self.vram_timer = QTimer(self)
        self.vram_timer.setInterval(1000)
        self.vram_timer.timeout.connect(self._poll_vram)
        self.vram_timer.start()

    def _poll_vram(self):
        if not self.ai:
            return
        # Use get_vram_usage_gb method
        used, total = self.ai.get_vram_usage_gb()
        self._on_vram(used, total)

    def _set_status(self, s):
        self.status_label.setText(s)
        self.footer_status.setText(s)

    def _on_benchmark(self, tps):
        self.benchmark_label.setText(f"Speed: {tps} t/s")

    def _on_vram(self, used, total):
        try:
            self.vram_label.setText(f"VRAM: {used} / {total} GB")
            self.footer_vram.setText(f"{used:.2f}/{total:.1f} GB")
        except Exception:
            pass

    def _on_model_ready(self):
        self.status_label.setText("● Ready")
        self.status_label.setStyleSheet("color:#4CAF50; font-weight:600;")
        self.progress.hide()
        # update vram & benchmark
        self.ai._emit_vram()

    # ----------------- messaging -----------------
    def add_user_message(self, text):
        f = QFrame()
        f.setStyleSheet("background:#6e8bff; border-radius:12px; padding:10px;")
        l = QVBoxLayout(f)
        lbl = QLabel(text)
        lbl.setStyleSheet("color:white;")
        lbl.setWordWrap(True)
        l.addWidget(lbl)
        container = QHBoxLayout()
        container.addStretch()
        container.addWidget(f, stretch=3)
        w = QWidget(); w.setLayout(container)
        self.console_layout.addWidget(w)

    def add_ai_message(self, text):
        f = QFrame()
        f.setStyleSheet("border:1px solid #2b3548; border-radius:12px; padding:10px;")
        l = QVBoxLayout(f)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        l.addWidget(lbl)
        container = QHBoxLayout()
        container.addWidget(f, stretch=3)
        container.addStretch()
        w = QWidget(); w.setLayout(container)
        self.console_layout.addWidget(w)

    def send_message(self):
        if not self.ai or not self.ai.is_loaded:
            self.add_ai_message("⚠️ Model not loaded yet.")
            return
        text = self.input.text().strip()
        if not text:
            return
        self.add_user_message(text)
        self.input.clear()
        self.input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("● Processing...")
        self.status_label.setStyleSheet("color:#FFA726; font-weight:600;")
        # pull generation settings from settings file
        max_tokens = int(self.settings.get("max_tokens", 256))
        temp = float(self.settings.get("temperature", 0.7))
        self.current_worker = AIWorker(self.ai, text, max_new_tokens=max_tokens, temperature=temp)
        self.current_worker.response_ready.connect(self._on_response)
        self.current_worker.start()

    def _on_response(self, resp):
        self.add_ai_message(resp)
        self.input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("● Ready")
        self.status_label.setStyleSheet("color:#4CAF50; font-weight:600;")
        # scroll to bottom
        try:
            sb = self.console_content.parent().parent().verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            pass

    def stop_generation(self):
        if self.current_worker and self.current_worker.isRunning():
            # best-effort stop; threads can't be killed cleanly. The worker supports a stop flag.
            try:
                self.current_worker.stop()
            except Exception:
                pass
            self.status_label.setText("● Stopped")
            self.stop_btn.setEnabled(False)
            self.send_btn.setEnabled(True)
            self.input.setEnabled(True)

    def _on_model_change(self, key):
        # user chose different model; let Nova handle unload/load
        if not self.ai:
            return
        self.progress.show()
        self.progress.setValue(1)
        self.ai.switch_model(key)
        # UI will reflect progress via callbacks
        self.add_ai_message(f"🔄 Switching to {key}...")