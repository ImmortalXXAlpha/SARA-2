# ui/ai_console_page.py
"""
Optimized AI Console with tool integration.
Key optimizations:
- Lazy widget creation
- Efficient message rendering  
- Fast keyword matching before AI inference
- Reduced timer overhead
- Better memory management
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QFrame, QLineEdit, QComboBox, QScrollArea, 
    QProgressBar, QSizePolicy, QScroller
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot, QMetaObject, Q_ARG
from PySide6.QtGui import QTextCursor
import os
import json
import threading

# Import coordinator
from ai.ai_tool_coordinator import AIToolCoordinator, OptimizedAIWorker


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
            
        # Check for tool commands first (fast, no AI needed)
        if self.coordinator:
            tool_response, tool_match = self.coordinator.process_message(self.prompt)
            if tool_response:
                self.response_ready.emit(tool_response)
                return
        
        # No tool match - run AI inference
        if self._stopped:
            return
        result = self.ai.generate(
            self.prompt, 
            max_new_tokens=self.max_new_tokens, 
            temperature=self.temperature
        )
        if not self._stopped:
            self.response_ready.emit(result)


class AIConsolePage(QWidget):
    # Signal to trigger tools from coordinator
    trigger_tool = Signal(str)
    
    def __init__(self, ai=None, clean_tune_page=None):
        super().__init__()
        self.ai = ai
        self.clean_tune_page = clean_tune_page
        self.current_worker = None
        self.settings_path = os.path.join(os.path.expanduser("~"), ".sara_settings.json")
        self.settings = self._load_settings()
        
        # Create tool coordinator
        self.coordinator = AIToolCoordinator(ai=ai, clean_tune_page=clean_tune_page)
        self.coordinator.tool_requested.connect(self._on_tool_requested)
        
        # Message buffer for efficient rendering
        self._message_widgets = []
        self._max_messages = 100  # Limit for memory management
        
        self._init_ui()
        self._wire_ai_callbacks()
        
        # Auto-start load if needed (delayed to not block UI)
        if self.ai and not self.ai.is_loaded and not self.ai.is_loading:
            QTimer.singleShot(100, self.ai.start_load)

    def set_clean_tune_page(self, page):
        """Set the CleanTunePage reference for tool execution."""
        self.clean_tune_page = page
        self.coordinator.set_clean_tune_page(page)

    def _load_settings(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header row
        header = QHBoxLayout()
        title = QLabel("🤖 AI Console (Local)")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        # Model selector
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

        # Info row (VRAM / benchmark) - simplified
        info_row = QHBoxLayout()
        self.vram_label = QLabel("VRAM: - / -")
        self.benchmark_label = QLabel("Speed: - t/s")
        info_row.addWidget(self.vram_label)
        info_row.addStretch()
        info_row.addWidget(self.benchmark_label)
        layout.addLayout(info_row)

        # Progress bar (hidden by default)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        # Console area - use QTextEdit for better performance
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            QTextEdit {
                background: #121826;
                border: 1px solid #2b3548;
                border-radius: 10px;
                padding: 12px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
        """)
        # Enable kinetic scrolling for smoother experience
        QScroller.grabGesture(self.console.viewport(), QScroller.LeftMouseButtonGesture)
        layout.addWidget(self.console, 1)

        # Input row
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask SARA to run scans, cleanup, or ask about your system...")
        self.input.setStyleSheet("""
            QLineEdit {
                background: #0f1522;
                border: 1px solid #2b3548;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
            }
            QLineEdit:focus { border-color: #6e8bff; }
        """)
        self.input.returnPressed.connect(self.send_message)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #6e8bff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover { background: #869eff; }
            QPushButton:disabled { background: #3d4a6b; }
        """)
        self.send_btn.clicked.connect(self.send_message)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #ff6e6e;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background: #ff8a8a; }
        """)
        self.stop_btn.clicked.connect(self.stop_generation)
        self.stop_btn.setEnabled(False)
        
        input_row.addWidget(self.input, 5)
        input_row.addWidget(self.send_btn, 1)
        input_row.addWidget(self.stop_btn, 1)
        layout.addLayout(input_row)

        # Quick action buttons
        quick_row = QHBoxLayout()
        quick_label = QLabel("Quick actions:")
        quick_label.setStyleSheet("color: #9eb3ff; font-size: 12px;")
        quick_row.addWidget(quick_label)
        
        quick_actions = [
            ("🔍 Run SFC", "run system file checker"),
            ("🛠️ DISM Repair", "run dism repair"),
            ("🧹 Cleanup", "cleanup temp files"),
            ("🛡️ Virus Scan", "scan for viruses"),
        ]
        for label, cmd in quick_actions:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background: #1b2230;
                    color: #cfd7ff;
                    border: 1px solid #2b3548;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                }
                QPushButton:hover { background: #2b3548; border-color: #6e8bff; }
            """)
            btn.clicked.connect(lambda _, c=cmd: self._quick_action(c))
            quick_row.addWidget(btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        self.setLayout(layout)
        
        # Add welcome message
        self._append_system_message(
            "👋 Welcome to SARA AI Console!\n\n"
            "I can help you with:\n"
            "• **System repairs** - Run SFC or DISM to fix Windows issues\n"
            "• **Disk cleanup** - Remove temp files and free space\n"
            "• **Security scans** - Check files with VirusTotal\n"
            "• **General questions** - Ask me anything about your system\n\n"
            "Try the quick action buttons below, or just ask me what you need!"
        )

    def _wire_ai_callbacks(self):
        if not self.ai:
            return
        self.ai.on_progress = self._on_progress
        self.ai.on_status = self._set_status
        self.ai.on_loaded = self._on_model_ready
        self.ai.on_benchmark = self._on_benchmark
        self.ai.on_vram = self._on_vram

        # Reduced polling frequency (every 2s instead of 1s)
        self.vram_timer = QTimer(self)
        self.vram_timer.setInterval(2000)
        self.vram_timer.timeout.connect(self._poll_vram)
        self.vram_timer.start()

    @Slot(int)
    def _on_progress(self, v):
        self.progress.setValue(v)
        if v > 0 and v < 100:
            self.progress.show()
        elif v >= 100:
            self.progress.hide()

    def _poll_vram(self):
        if self.ai:
            used, total = self.ai.get_vram_usage_gb()
            self._on_vram(used, total)

    def _set_status(self, s):
        self.status_label.setText(s)

    def _on_benchmark(self, tps):
        self.benchmark_label.setText(f"Speed: {tps} t/s")

    def _on_vram(self, used, total):
        if total > 0:
            self.vram_label.setText(f"VRAM: {used:.2f} / {total:.1f} GB")
        else:
            self.vram_label.setText("VRAM: CPU mode")

    def _on_model_ready(self):
        self.status_label.setText("● Ready")
        self.status_label.setStyleSheet("color:#4CAF50; font-weight:600;")
        self.progress.hide()
        self._append_system_message(f"✅ Model **{self.ai.model_key}** loaded and ready!")

    # ---- Messaging ----
    def _append_user_message(self, text):
        html = f"""
        <div style="text-align: right; margin: 8px 0;">
            <span style="background: #6e8bff; color: white; padding: 10px 14px; 
                        border-radius: 12px; display: inline-block; max-width: 70%;">
                {text}
            </span>
        </div>
        """
        self.console.append(html)
        self._scroll_to_bottom()

    def _append_ai_message(self, text):
        # Convert markdown-style bold to HTML
        text = text.replace("**", "<b>", 1)
        while "**" in text:
            text = text.replace("**", "</b>", 1).replace("**", "<b>", 1)
        text = text.replace("\n", "<br>")
        
        html = f"""
        <div style="text-align: left; margin: 8px 0;">
            <span style="background: #1b2230; border: 1px solid #2b3548; color: #e8eef6; 
                        padding: 10px 14px; border-radius: 12px; display: inline-block; max-width: 80%;">
                🤖 {text}
            </span>
        </div>
        """
        self.console.append(html)
        self._scroll_to_bottom()

    def _append_system_message(self, text):
        text = text.replace("**", "<b>", 1)
        while "**" in text:
            text = text.replace("**", "</b>", 1).replace("**", "<b>", 1)
        text = text.replace("\n", "<br>")
        
        html = f"""
        <div style="text-align: center; margin: 12px 0;">
            <span style="background: #0f1522; border: 1px dashed #2b3548; color: #9eb3ff; 
                        padding: 10px 16px; border-radius: 8px; display: inline-block; font-size: 13px;">
                {text}
            </span>
        </div>
        """
        self.console.append(html)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.console.setTextCursor(cursor)

    def _quick_action(self, command):
        self.input.setText(command)
        self.send_message()

    def send_message(self):
        if not self.ai:
            self._append_ai_message("⚠️ AI backend not connected.")
            return
        if not self.ai.is_loaded:
            self._append_ai_message("⚠️ Model is still loading. Please wait...")
            return
            
        text = self.input.text().strip()
        if not text:
            return
            
        self._append_user_message(text)
        self.input.clear()
        self.input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("● Processing...")
        self.status_label.setStyleSheet("color:#FFA726; font-weight:600;")

        max_tokens = int(self.settings.get("max_tokens", 256))
        temp = float(self.settings.get("temperature", 0.7))
        
        self.current_worker = AIWorker(
            self.ai, text, 
            coordinator=self.coordinator,
            max_new_tokens=max_tokens, 
            temperature=temp
        )
        self.current_worker.response_ready.connect(self._on_response)
        self.current_worker.start()

    def _on_response(self, resp):
        self._append_ai_message(resp)
        self.input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("● Ready")
        self.status_label.setStyleSheet("color:#4CAF50; font-weight:600;")

    def stop_generation(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.stop()
            self.status_label.setText("● Stopped")
            self.stop_btn.setEnabled(False)
            self.send_btn.setEnabled(True)
            self.input.setEnabled(True)

    def _on_model_change(self, key):
        if not self.ai:
            return
        self.progress.show()
        self.progress.setValue(1)
        self.ai.switch_model(key)
        self._append_system_message(f"🔄 Switching to **{key}**...")

    @Slot(str, dict)
    def _on_tool_requested(self, tool_name: str, options: dict):
        """Handle tool execution request from coordinator."""
        if self.clean_tune_page:
            # Use QMetaObject.invokeMethod for thread-safe UI call
            QTimer.singleShot(0, lambda: self.clean_tune_page._start_tool(tool_name))