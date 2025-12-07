# ui/clean_tune_page.py
"""
Enhanced Clean & Tune Page with AI-powered threat analysis.
"""

import os
import re
import time
import hashlib
import threading
import subprocess
from datetime import datetime

import requests
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QPropertyAnimation, QThread, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QTextEdit, QDialog, QFileDialog,
    QHBoxLayout, QCheckBox, QDialogButtonBox, QMessageBox,
    QGraphicsOpacityEffect, QApplication, QScrollArea, QSplitter
)

# VirusTotal API Key
VT_API_KEY = os.getenv("VT_API_KEY", "").strip()
if not VT_API_KEY:
    #VT_API_KEY = "2bfe6972b6f0cfe9dd9b067fee7b1b5b0b7f6f1fe765c88d1750faf8333a7a9a" #John's
    VT_API_KEY = "b2a200436bea951ded7e32d851c3953d516b05078e6aea29485dde3e80c791e5" #Mango's


class LogWindow(QDialog):
    closed = Signal()
    finished = Signal(bool, str)

    def __init__(self, title: str, tool_name: str = None):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(800, 520)
        
        self._success = False
        self._message = ""
        self._auto_close = False
        self._tool_name = tool_name
        self._workflow_mode = False
        self._is_closing = False  # NEW: Prevent double-close
        
        # Completion detector
        from ui.clean_tune_page import ToolCompletionDetector
        self._detector = ToolCompletionDetector(tool_name) if tool_name else None

        v = QVBoxLayout(self)
        self.text = QTextEdit(readOnly=True)
        self.text.setStyleSheet("""
            QTextEdit {
                background: #0f1522;
                border: 1px solid #2b3548;
                border-radius: 8px;
                padding: 10px;
                color: #e8eef6;
                font-family: 'Consolas', monospace;
            }
        """)
        v.addWidget(self.text)

        self.timer_label = QLabel("⏱ Elapsed: 0s")
        self.timer_label.setStyleSheet("color:#9eb3ff; font-size:13px;")
        v.addWidget(self.timer_label)

        self._start = datetime.now()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        
        # Auto-close timer
        self._auto_close_timer = None

    def _tick(self):
        secs = int((datetime.now() - self._start).total_seconds())
        self.timer_label.setText(f"⏱ Elapsed: {secs}s")
        
        # Check if detector says we're complete
        if self._detector and self._detector.is_complete and not self._auto_close_timer:
            # Tool completed - set result and prepare to auto-close
            self.set_result(self._detector.success, self._detector.message)
            
            # In workflow mode, auto-close after short delay
            if hasattr(self, '_workflow_mode') and self._workflow_mode:
                self.set_auto_close(True, delay_ms=2000)

    def append(self, s: str):
        if s:
            self.text.append(s)
            self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
            
            # Feed to detector
            if self._detector:
                self._detector.add_line(s)

    def stop_timer(self):
        if self._timer.isActive():
            self._timer.stop()
        if self._auto_close_timer:
            self._auto_close_timer.stop()
    
    def set_result(self, success: bool, message: str):
        """Set the result of the operation."""
        # Only set once (first result wins)
        if not self._message:
            self._success = success
            self._message = message
            
            # Update window title to show status
            status_icon = "✅" if success else "❌"
            self.setWindowTitle(f"{status_icon} {self.windowTitle()}")
    
    def set_workflow_mode(self, enabled: bool):
        """Enable workflow mode for this window."""
        self._workflow_mode = enabled
    
    def set_auto_close(self, auto_close: bool, delay_ms: int = 2000):
        """Enable auto-close after completion."""
        if auto_close and not self._auto_close_timer:
            self._auto_close_timer = QTimer(self)
            self._auto_close_timer.setSingleShot(True)
            self._auto_close_timer.timeout.connect(self.close)
            self._auto_close_timer.start(delay_ms)
    
    def force_completion_check(self):
        """Force a final completion check when process ends."""
        if self._detector:
            self._detector.force_check_completion()
            if not self._message:  # If result not already set
                self.set_result(self._detector.success, self._detector.message)

    def closeEvent(self, e):
        """Handle window close with proper cleanup."""
        if hasattr(self, '_is_closing') and self._is_closing:
            e.accept()
            return
        
        self._is_closing = True
        
        # Stop timer
        if hasattr(self, '_timer') and self._timer:
            self._timer.stop()
            self._timer = None
        
        if hasattr(self, '_auto_close_timer') and self._auto_close_timer:
            self._auto_close_timer.stop()
            self._auto_close_timer = None
        
        # If no result set yet, mark as cancelled
        if not self._message:
            self._success = False
            self._message = "Cancelled by user"
        
        # Emit signals in try-catch
        try:
            self.finished.emit(self._success, self._message)
        except RuntimeError:
            pass  # Signal disconnected, ignore
        
        try:
            self.closed.emit()
        except RuntimeError:
            pass  # Signal disconnected, ignore
        
        # Clear detector reference
        if hasattr(self, '_detector'):
            self._detector = None
        
        e.accept()

class ToolCompletionDetector:
    """
    Detects when tools complete and determines success/failure from output.
    """
    
    # Completion patterns for each tool
    COMPLETION_PATTERNS = {
        "System File Checker (SFC)": {
            "success": [
                "verification 100% complete",
                "did not find any integrity violations",
                "successfully repaired",
                "windows resource protection found corrupt files and successfully repaired them"
            ],
            "failure": [
                "windows resource protection found corrupt files but was unable to fix",
                "could not perform the requested operation",
                "windows resource protection could not start the repair service"
            ],
            "info": [
                "windows resource protection did not find any integrity violations"
            ]
        },
        "DISM Repair": {
            "success": [
                "operation completed successfully",
                "the restore operation completed successfully",
                "the operation completed successfully"
            ],
            "failure": [
                "error:",
                "failed",
                "the operation failed",
                "could not"
            ],
            "info": [
                "no component store corruption detected"
            ]
        },
        "Cleanup Temp Files": {
            "success": [
                "✅ cleanup complete",
                "cleanup complete"
            ],
            "failure": [
                "cleanup failed:",
                "error:"
            ],
            "info": []
        },
        "SmartScan (VirusTotal)": {
            "success": [
                "scan complete:",
                "all files clean"
            ],
            "failure": [
                "smartscan aborted",
                "failed to get admin"
            ],
            "info": [
                "flagged out of"
            ]
        }
    }
    
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.output_buffer = []
        self.max_buffer_size = 50  # Keep last 50 lines
        self.is_complete = False
        self.success = False
        self.message = ""
    
    def add_line(self, line: str):
        """Add a line of output and check for completion."""
        if not line or not line.strip():
            return
        
        # Add to buffer
        self.output_buffer.append(line.lower())
        if len(self.output_buffer) > self.max_buffer_size:
            self.output_buffer.pop(0)
        
        # Check if tool has completed
        if not self.is_complete:
            self._check_completion()
    
    def _check_completion(self):
        """Check if tool has completed based on output patterns."""
        patterns = self.COMPLETION_PATTERNS.get(self.tool_name, {})
        
        # Get last 10 lines for checking
        recent_output = "\n".join(self.output_buffer[-10:])
        
        # Check for success patterns
        for pattern in patterns.get("success", []):
            if pattern.lower() in recent_output:
                self.is_complete = True
                self.success = True
                self.message = self._extract_message(pattern)
                return
        
        # Check for info patterns (also success, but with context)
        for pattern in patterns.get("info", []):
            if pattern.lower() in recent_output:
                self.is_complete = True
                self.success = True
                self.message = self._extract_message(pattern)
                return
        
        # Check for failure patterns
        for pattern in patterns.get("failure", []):
            if pattern.lower() in recent_output:
                self.is_complete = True
                self.success = False
                self.message = self._extract_message(pattern)
                return
    
    def _extract_message(self, pattern: str) -> str:
        """Extract a meaningful message based on the pattern matched."""
        # Find the line containing the pattern
        for line in reversed(self.output_buffer):
            if pattern.lower() in line:
                # Clean up and return the line
                return line.strip()
        return pattern
    
    def force_check_completion(self):
        """Force a completion check (called when process ends)."""
        if not self.is_complete:
            self._check_completion()
        
        # If still not marked complete after process ends, check return code context
        if not self.is_complete:
            # Look for generic completion indicators
            recent = "\n".join(self.output_buffer[-5:])
            if any(word in recent for word in ["complete", "finished", "done", "success"]):
                self.is_complete = True
                self.success = True
                self.message = "Completed"
            else:
                self.is_complete = True
                self.success = False
                self.message = "Completed with unknown status"


class WorkerSignals(QObject):
    progress = Signal(int)
    message = Signal(str)
    done = Signal(bool, str)
    results = Signal(object)
    line_added = Signal(str)


class AdvancedCleanupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Cleanup Options")
        self.setMinimumWidth(460)

        v = QVBoxLayout(self)
        desc = QLabel("Select extras to clear. Defaults are safe Windows caches only.")
        desc.setStyleSheet("color:#cfd7ff;")
        v.addWidget(desc)

        self.chk_chrome = QCheckBox("Include Chrome cache")
        self.chk_edge = QCheckBox("Include Edge cache")
        self.chk_firefox = QCheckBox("Include Firefox cache")
        for c in (self.chk_chrome, self.chk_edge, self.chk_firefox):
            c.setStyleSheet("color:#e8eef6;")
            v.addWidget(c)

        hint = QLabel("Note: clearing browser caches may log you out of some sites.")
        hint.setStyleSheet("color:#8aa0ff; font-size:12px; font-style:italic;")
        v.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def selections(self):
        return {
            "chrome": self.chk_chrome.isChecked(),
            "edge": self.chk_edge.isChecked(),
            "firefox": self.chk_firefox.isChecked(),
        }


class AIThreatAnalyzer(QThread):
    """Analyzes flagged files with AI to explain threats."""
    finished = Signal(str)
    
    def __init__(self, ai, flagged_files):
        super().__init__()
        self.ai = ai
        self.flagged_files = flagged_files
    
    def run(self):
        if not self.ai or not getattr(self.ai, 'is_loaded', False):
            self.finished.emit("")
            return
        
        if not self.flagged_files:
            self.finished.emit("No flagged files to analyze.")
            return
        
        try:
            file_info = []
            for f in self.flagged_files[:10]:  # Limit for context
                file_info.append(
                    f"- {f.get('name', 'Unknown')} (flagged by {f.get('malicious', 0)} engines)\n"
                    f"  Path: {f.get('path', 'Unknown')}\n"
                    f"  Extension: {os.path.splitext(f.get('name', ''))[1] or 'none'}"
                )
            
            files_text = "\n".join(file_info)
            
            prompt = f"""You are a cybersecurity expert helping a user understand potential threats on their computer.

These files were flagged by VirusTotal antivirus engines:

{files_text}

For each file, provide:
1. **Risk Assessment**: Is this likely a real threat or a false positive? (High/Medium/Low risk)
2. **Explanation**: What type of threat could this be? (malware type, adware, PUP, etc.)
3. **Context**: Are files with this name/extension commonly flagged incorrectly?
4. **Recommendation**: Should the user delete it, quarantine it, or is it likely safe?

Be helpful but cautious - when in doubt, recommend deletion or professional help.
Keep explanations simple for non-technical users."""

            response = self.ai.generate(prompt, max_new_tokens=600, temperature=0.4)
            self.finished.emit(response)
            
        except Exception as e:
            self.finished.emit(f"AI analysis failed: {e}")


class ReviewDialog(QDialog):
    """Review flagged files with AI analysis and selective deletion."""

    def __init__(self, flagged_list, ai=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛡️ Review Flagged Files")
        self.setMinimumSize(850, 600)
        self.flagged = flagged_list or []
        self.ai = ai
        self._checkboxes = []
        self._ai_analyzer = None
        self._init_ui()
        
        # Start AI analysis if available
        if self.ai and self.flagged:
            self._start_ai_analysis()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel(
            "⚠️ The following files were flagged by VirusTotal.\n"
            "Review carefully before deleting. Nothing is removed automatically."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color:#ffb347; font-size:14px; font-weight:500;")
        layout.addWidget(header)

        # Main splitter
        splitter = QSplitter(Qt.Vertical)

        # AI Analysis section
        ai_frame = QFrame()
        ai_frame.setStyleSheet("QFrame { background: #1b2230; border-radius: 10px; }")
        ai_layout = QVBoxLayout(ai_frame)
        ai_layout.setContentsMargins(15, 15, 15, 15)
        
        ai_header = QHBoxLayout()
        ai_header.addWidget(QLabel("🤖 AI Threat Analysis"))
        self.ai_status = QLabel("")
        self.ai_status.setStyleSheet("color: #9eb3ff; font-style: italic;")
        ai_header.addStretch()
        ai_header.addWidget(self.ai_status)
        ai_layout.addLayout(ai_header)
        
        self.ai_analysis = QTextEdit()
        self.ai_analysis.setReadOnly(True)
        self.ai_analysis.setPlaceholderText(
            "AI analysis will appear here...\n\n"
            "If no AI model is loaded, you can still review files manually below."
        )
        self.ai_analysis.setStyleSheet("""
            QTextEdit {
                background: #0f1522;
                border: 1px solid #2b3548;
                border-radius: 8px;
                padding: 12px;
                color: #e8eef6;
            }
        """)
        self.ai_analysis.setMinimumHeight(150)
        ai_layout.addWidget(self.ai_analysis)
        splitter.addWidget(ai_frame)

        # File list section
        files_frame = QFrame()
        files_frame.setStyleSheet("QFrame { background: #1b2230; border-radius: 10px; }")
        files_layout = QVBoxLayout(files_frame)
        files_layout.setContentsMargins(15, 15, 15, 15)
        
        files_header = QHBoxLayout()
        files_header.addWidget(QLabel(f"📁 Flagged Files ({len(self.flagged)})"))
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setFixedWidth(100)
        self.select_all_btn.clicked.connect(self._toggle_all)
        files_header.addStretch()
        files_header.addWidget(self.select_all_btn)
        files_layout.addLayout(files_header)
        
        # Scrollable file list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #1b2230;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #3d4a6b;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #6e8bff; }
        """)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(5, 5, 5, 5)

        for item in self.flagged:
            file_widget = self._create_file_widget(item)
            content_layout.addWidget(file_widget)

        if not self.flagged:
            none_label = QLabel("✅ No flagged files to review.")
            none_label.setStyleSheet("color:#4CAF50; font-size:14px;")
            content_layout.addWidget(none_label)

        content_layout.addStretch()
        scroll.setWidget(content)
        files_layout.addWidget(scroll)
        splitter.addWidget(files_frame)
        
        splitter.setSizes([250, 300])
        layout.addWidget(splitter, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        
        self.open_folder_btn = QPushButton("📂 Open Folder")
        self.open_folder_btn.clicked.connect(self._open_containing_folder)
        
        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #c0392b;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover { background: #e74c3c; }
            QPushButton:disabled { background: #555; }
        """)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def _create_file_widget(self, item):
        """Create a styled widget for each flagged file."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #0f1522;
                border: 1px solid #2b3548;
                border-radius: 8px;
                padding: 5px;
            }
            QFrame:hover { border-color: #6e8bff; }
        """)
        
        h_layout = QHBoxLayout(frame)
        h_layout.setContentsMargins(10, 8, 10, 8)
        
        cb = QCheckBox()
        cb.setChecked(True)
        h_layout.addWidget(cb)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name = item.get("name", "Unknown")
        path = item.get("path", "")
        bad = item.get("malicious", 0)
        
        # Risk color
        if bad >= 10:
            risk_color = "#e74c3c"
            risk_text = "HIGH RISK"
        elif bad >= 5:
            risk_color = "#e67e22"
            risk_text = "MEDIUM RISK"
        else:
            risk_color = "#f39c12"
            risk_text = "LOW RISK"
        
        name_label = QLabel(f"<b>{name}</b>  <span style='color:{risk_color};'>({bad} detections - {risk_text})</span>")
        name_label.setStyleSheet("color: #e8eef6;")
        
        path_label = QLabel(path)
        path_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        path_label.setWordWrap(True)
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(path_label)
        h_layout.addLayout(info_layout, 1)
        
        self._checkboxes.append((cb, path, frame))
        return frame

    def _toggle_all(self):
        all_checked = all(cb.isChecked() for cb, _, _ in self._checkboxes)
        for cb, _, _ in self._checkboxes:
            cb.setChecked(not all_checked)
        self.select_all_btn.setText("Deselect All" if not all_checked else "Select All")

    def _start_ai_analysis(self):
        if not self.ai or not getattr(self.ai, 'is_loaded', False):
            self.ai_analysis.setPlainText(
                "⚠️ AI model not loaded.\n\n"
                "To get AI-powered threat analysis:\n"
                "1. Go to AI Console and wait for model to load\n"
                "2. Run the scan again\n\n"
                "You can still review files manually below."
            )
            return
        
        self.ai_status.setText("Analyzing...")
        self.ai_analysis.setPlainText("🔄 AI is analyzing the flagged files...")
        
        self._ai_analyzer = AIThreatAnalyzer(self.ai, self.flagged)
        self._ai_analyzer.finished.connect(self._on_ai_finished)
        self._ai_analyzer.start()

    @Slot(str)
    def _on_ai_finished(self, analysis):
        self.ai_status.setText("Complete")
        if analysis:
            self.ai_analysis.setPlainText(analysis)
        else:
            self.ai_analysis.setPlainText("Could not generate AI analysis.")

    def _open_containing_folder(self):
        if self.flagged:
            folder = os.path.dirname(self.flagged[0].get("path", ""))
            if folder and os.path.exists(folder):
                os.startfile(folder) if os.name == 'nt' else None

    def _on_delete_clicked(self):
        selected = [(cb, p) for cb, p, _ in self._checkboxes if cb.isChecked() and p]
        if not selected:
            QMessageBox.information(self, "No Selection", "No files selected for deletion.")
            return

        count = len(selected)
        resp = QMessageBox.warning(
            self, "⚠️ Confirm Deletion",
            f"Are you sure you want to PERMANENTLY delete {count} file(s)?\n\n"
            "This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if resp != QMessageBox.Yes:
            return

        self.delete_btn.setEnabled(False)
        self.close_btn.setEnabled(False)

        deleted = 0
        failed = []
        
        for cb, path in selected:
            try:
                if os.path.exists(path) and os.path.isfile(path):
                    os.remove(path)
                    deleted += 1
                    # Gray out the deleted item
                    for checkbox, p, frame in self._checkboxes:
                        if p == path:
                            frame.setStyleSheet("QFrame { background: #1a1a1a; opacity: 0.5; }")
                            checkbox.setEnabled(False)
                            break
            except Exception as e:
                failed.append(f"{os.path.basename(path)}: {e}")

        self.delete_btn.setEnabled(True)
        self.close_btn.setEnabled(True)

        if failed:
            QMessageBox.warning(
                self, "Deletion Results",
                f"Deleted {deleted}/{count} files.\n\nFailed:\n" + "\n".join(failed)
            )
        else:
            QMessageBox.information(self, "Success", f"Successfully deleted {deleted} file(s).")


class CleanTunePage(QWidget):
    def __init__(self, ai=None):
        super().__init__()
        self.ai = ai
        self._active_proc = None
        self._active_timer = None
        self._active_log = None
        self._current_log = None
        self._in_workflow_mode = False
        self._active_threads = []  # NEW: Track active threads
        self._init_ui()

    def set_ai(self, ai):
        self.ai = ai

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(25)

        title = QLabel("🧹 System Clean & Tune")
        title.setObjectName("title")
        sub = QLabel("Run maintenance tools to optimize your system")
        sub.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(sub)

        grid = QGridLayout()
        grid.setSpacing(25)

    

        self.tools = {
            "System File Checker (SFC)": {
                "desc": "Scans and repairs corrupted system files",
                "ps": "sfc /scannow",
                "icon": "🔧"
            },
            "DISM Repair": {
                "desc": "Repairs Windows system image",
                "ps": "DISM /Online /Cleanup-Image /RestoreHealth",
                "icon": "🛠️"
            },
            "Cleanup Temp Files": {
                "desc": "Removes temporary files and caches",
                "ps": None,
                "icon": "🧹"
            },
            "SmartScan (VirusTotal)": {
                "desc": "AI-powered virus scan with VirusTotal",
                "ps": None,
                "icon": "🛡️"
            },
        }

        self.progress_bars = {}
        self.time_labels = {}

        r = c = 0
        for name, meta in self.tools.items():
            card, pbar, tlabel = self._make_card(name, meta["desc"], meta.get("icon", ""))
            self.progress_bars[name] = pbar
            self.time_labels[name] = tlabel
            grid.addWidget(card, r, c)
            c = (c + 1) % 2
            if c == 0:
                r += 1

        root.addLayout(grid)
        root.addStretch()

    def _cleanup_thread(self, thread):
        """Safely cleanup a finished thread."""
        try:
            if thread and thread.isRunning():
                thread.quit()
                thread.wait(1000)  # Wait up to 1 second
            if thread in self._active_threads:
                self._active_threads.remove(thread)
        except:
            pass

    def _make_card(self, title, desc, icon=""):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border: 1px solid #2b3548;
                border-radius: 12px;
            }
            QFrame:hover { border-color: #6e8bff; }
        """)
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        t = QLabel(f"{icon} {title}" if icon else title)
        t.setStyleSheet("font-size:16px; font-weight:600; color:#fff;")
        d = QLabel(desc)
        d.setStyleSheet("color:#cfd7ff; font-size:13px;")
        d.setWordWrap(True)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet("""
            QProgressBar { background:#11151f; border-radius:4px; }
            QProgressBar::chunk { background:#6e8bff; border-radius:4px; }
        """)

        tl = QLabel("⏱ 00:00")
        tl.setStyleSheet("color:#8aa0ff; font-size:12px;")

        row = QHBoxLayout()
        row.addWidget(bar)
        row.addWidget(tl)
        row.setStretch(0, 5)
        row.setStretch(1, 1)

        btn = QPushButton("▶ Run Tool")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: #6e8bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: 600;
            }
            QPushButton:hover { background: #869eff; }
        """)
        btn.clicked.connect(lambda _, n=title: self._start_tool(n))

        v.addWidget(t)
        v.addWidget(d)
        v.addLayout(row)
        v.addStretch()
        v.addWidget(btn)
        return card, bar, tl

    def _start_tool(self, tool_name: str):
        # Check if in workflow mode
        in_workflow = hasattr(self, '_in_workflow_mode') and self._in_workflow_mode
        
        pbar = self.progress_bars[tool_name]
        tlab = self.time_labels[tool_name]
        pbar.setValue(0)
        tlab.setText("⏱ 00:00")

        # Create log window with tool name for detector
        log = LogWindow(tool_name, tool_name=tool_name)
        
        # Set workflow mode on window
        if in_workflow:
            log.set_workflow_mode(True)
        
        log.append(f"▶ {tool_name} started...\n")
        log.show()

        self._active_log = log
        start = datetime.now()
        card_timer = QTimer(self)
        card_timer.timeout.connect(lambda: self._update_elapsed(tlab, start))
        card_timer.start(1000)
        self._active_timer = card_timer

        def stop_running():
            if self._active_proc and self._active_proc.poll() is None:
                try:
                    self._active_proc.terminate()
                except:
                    pass
            if card_timer.isActive():
                card_timer.stop()
            tlab.setText("⏱ canceled")

        log.closed.connect(stop_running)

        sig = WorkerSignals()
        sig.progress.connect(pbar.setValue)
        sig.message.connect(log.append)
        sig.done.connect(lambda ok, msg: self._finish(ok, msg, tool_name, log, card_timer, tlab))
        
        self._current_log = log
        sig.results.connect(self._on_scan_results)

        if tool_name == "SmartScan (VirusTotal)":
            if QApplication.keyboardModifiers() & Qt.ShiftModifier:
                folder = QFileDialog.getExistingDirectory(self, "Select Folder to Scan")
                if not folder:
                    log.append("Scan cancelled.")
                    card_timer.stop()
                    return
            else:
                folder = os.path.join(os.path.expanduser("~"), "Downloads")
            
            log.append(f"📂 Scanning folder: {folder}\n")
            thread = threading.Thread(target=self._smartscan_worker, args=(folder, sig), daemon=True)
            self._active_threads.append(thread)  # Track it
            thread.start()

        elif tool_name == "Cleanup Temp Files":
            dlg = AdvancedCleanupDialog(self)
            if dlg.exec() != QDialog.Accepted:
                log.append("Cleanup cancelled.")
                card_timer.stop()
                return
            opts = dlg.selections()
            thread = threading.Thread(target=self._cleanup_worker, args=(opts, sig), daemon=True)
            self._active_threads.append(thread)  # Track it
            thread.start()

        else:
            ps_cmd = self.tools[tool_name]["ps"]
            thread = threading.Thread(target=self._powershell_worker, args=(ps_cmd, sig), daemon=True)
            self._active_threads.append(thread)  # Track it
            thread.start()

    def _powershell_worker(self, inner_cmd: str, sig: WorkerSignals):
        script = (
            "$ProgressPreference='SilentlyContinue'; "
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
            f"chcp 65001 > $null; {inner_cmd}"
        )

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", startupinfo=si, creationflags=flags
        )
        self._active_proc = proc

        percent_pat = re.compile(r'(\d{1,3})(?:\.\d+)?\s*%')
        for line in proc.stdout:
            clean = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", line).strip()
            if clean:
                sig.message.emit(clean)
                m = percent_pat.search(clean)
                if m:
                    sig.progress.emit(max(0, min(100, int(float(m.group(1))))))
        proc.wait()
        sig.done.emit(proc.returncode == 0, f"Finished with code {proc.returncode}")

    def _cleanup_worker(self, opts: dict, sig: WorkerSignals):
        """Fixed cleanup worker with proper PowerShell command separation."""
        
        # Build commands as a list - each is a separate statement
        commands = []
        commands.append('$ProgressPreference="SilentlyContinue"')
        commands.append('[Console]::OutputEncoding=[Text.Encoding]::UTF8')
        commands.append('chcp 65001 > $null')
        commands.append('Write-Output "Starting Cleanup..."')
        
        # TEMP files
        commands.append('Write-Output "Deleting TEMP files..."')
        commands.append('try { Remove-Item "$env:TEMP\\*" -Recurse -Force -EA SilentlyContinue } catch { }')
        
        # Prefetch
        commands.append('Write-Output "Deleting Prefetch..."')
        commands.append('try { Remove-Item "$env:SystemRoot\\Prefetch\\*" -Recurse -Force -EA SilentlyContinue } catch { }')
        
        # Windows Update cache
        commands.append('Write-Output "Deleting Update cache..."')
        commands.append('try { Remove-Item "$env:SystemRoot\\SoftwareDistribution\\Download\\*" -Recurse -Force -EA SilentlyContinue } catch { }')
        
        # Browser caches if selected
        if opts.get("chrome"):
            commands.append('Write-Output "Clearing Chrome cache..."')
            commands.append('try { Remove-Item "$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\Cache\\*" -Recurse -Force -EA SilentlyContinue } catch { }')
        
        if opts.get("edge"):
            commands.append('Write-Output "Clearing Edge cache..."')
            commands.append('try { Remove-Item "$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data\\Default\\Cache\\*" -Recurse -Force -EA SilentlyContinue } catch { }')
        
        if opts.get("firefox"):
            commands.append('Write-Output "Clearing Firefox cache..."')
            commands.append('try { Get-ChildItem "$env:APPDATA\\Mozilla\\Firefox\\Profiles" -Directory -EA SilentlyContinue | ForEach-Object { Remove-Item "$($_.FullName)\\cache2\\*" -Recurse -Force -EA SilentlyContinue } } catch { }')
        
        commands.append('Write-Output "✅ Cleanup complete."')
        
        # Join with semicolons - CRITICAL: This is the proper way
        script = "; ".join(commands)

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                encoding="utf-8", 
                startupinfo=si, 
                creationflags=flags
            )
            self._active_proc = proc

            # Read stdout
            for line in proc.stdout:
                clean = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", line).strip()
                if clean:
                    sig.message.emit(clean)
            
            # Wait for completion
            proc.wait()
            
            # Check stderr
            stderr_output = proc.stderr.read().strip()
            
            if proc.returncode == 0:
                sig.done.emit(True, "Cleanup completed successfully")
            else:
                if stderr_output:
                    sig.message.emit(f"\n⚠️ Warnings/Errors:\n{stderr_output}")
                sig.done.emit(False, f"Cleanup finished with warnings (exit code {proc.returncode})")
                
        except Exception as e:
            sig.message.emit(f"❌ Error: {e}")
            sig.done.emit(False, f"Cleanup failed: {e}")

    def _smartscan_worker(self, folder: str, sig: WorkerSignals):
        if not os.path.isdir(folder):
            sig.done.emit(False, "Folder not found.")
            return
        
        files = [os.path.join(folder, f) for f in os.listdir(folder) 
                 if os.path.isfile(os.path.join(folder, f))]
        
        if not files:
            sig.done.emit(False, "No files to scan.")
            return
        
        if not VT_API_KEY:
            sig.message.emit("⚠️ VirusTotal API key not configured.")
            sig.done.emit(False, "SmartScan aborted - no API key.")
            return

        sig.message.emit(f"Found {len(files)} files to scan...\n")
        
        flagged = []
        total = len(files)
        
        for i, path in enumerate(files, 1):
            name = os.path.basename(path)
            sig.message.emit(f"[{i}/{total}] Checking {name}...")
            
            try:
                h = self._hash_file(path)
            except Exception as e:
                sig.message.emit(f"  ⚠️ Error hashing: {e}")
                sig.progress.emit(int(i * 100 / total))
                continue

            try:
                data = self._vt_lookup(h)
                if data:
                    stats = data.get("attributes", {}).get("last_analysis_stats", {})
                    bad = int(stats.get("malicious", 0) or 0)
                    if bad > 0:
                        sig.message.emit(f"  🚨 FLAGGED by {bad} engine(s)!")
                        flagged.append({"path": path, "name": name, "malicious": bad})
                    else:
                        sig.message.emit(f"  ✅ Clean")
                else:
                    sig.message.emit(f"  ℹ️ Not in VT database")
            except Exception as e:
                sig.message.emit(f"  ⚠️ VT error: {e}")

            sig.progress.emit(int(i * 100 / total))
            time.sleep(0.3)  # Rate limiting

        sig.message.emit(f"\n{'='*40}")
        sig.message.emit(f"Scan complete: {len(flagged)} file(s) flagged out of {total}")
        
        # Emit results BEFORE done signal so dialog shows first
        if flagged:
            sig.results.emit(flagged)
            msg = f"🚨 {len(flagged)} threat(s) found! Review dialog opened."
        else:
            msg = "✅ All files clean!"
        
        sig.done.emit(True, msg)

    def _on_scan_results(self, results):
        """Slot to handle scan results - shows review dialog."""
        log = getattr(self, '_current_log', None)
        
        if not results:
            if log:
                log.append("No flagged files to review.")
            return
        
        if log:
            log.append(f"\n🔍 Found {len(results)} flagged file(s). Opening review dialog...")
        
        # Create and show review dialog
        try:
            dlg = ReviewDialog(results, ai=self.ai, parent=self)
            dlg.setModal(True)
            dlg.exec()
            if log:
                log.append("✅ Review dialog closed.")
        except Exception as e:
            if log:
                log.append(f"❌ Error opening review dialog: {e}")
            print(f"ReviewDialog error: {e}")

    def _handle_scan_results(self, results, log):
        """Show review dialog when flagged files are found."""
        if not results:
            log.append("No flagged files to review.")
            return
        
        log.append(f"\n🔍 Found {len(results)} flagged file(s). Opening review dialog...")
        
        # Create and show review dialog
        try:
            dlg = ReviewDialog(results, ai=self.ai, parent=self)
            dlg.setModal(True)
            dlg.exec()
            log.append("✅ Review dialog closed.")
        except Exception as e:
            log.append(f"❌ Error opening review dialog: {e}")

    def _finish(self, ok, msg, tool, log, card_timer, tlab):
        if card_timer.isActive():
            card_timer.stop()
        log.stop_timer()
        log.append(f"\n{msg}")
        log.append("-" * 40)
        
        # Force completion check
        if hasattr(log, 'force_completion_check'):
            log.force_completion_check()
        
        # Set result
        if hasattr(log, 'set_result'):
            log.set_result(ok, msg)
        
        # Update progress bar
        if ok:
            self.progress_bars[tool].setValue(100)
        
        # Check if in workflow mode
        in_workflow = hasattr(self, '_in_workflow_mode') and self._in_workflow_mode
        
        if not in_workflow:
            # Normal mode - show message boxes
            if ok:
                QMessageBox.information(self, "Complete", msg)
            else:
                QMessageBox.warning(self, "Issue Detected", msg)
        # In workflow mode, window will auto-close via detector
        
        self._fade_out_label(tlab)
        self._active_proc = None
        self._active_timer = None
        
        # NEW: Clean up any finished threads
        self._cleanup_finished_threads()

    def _cleanup_finished_threads(self):
        """Clean up threads that have finished."""
        for thread in list(self._active_threads):
            if not thread.is_alive():
                self._active_threads.remove(thread)

    def _update_elapsed(self, label, start):
        secs = int((datetime.now() - start).total_seconds())
        m, s = divmod(secs, 60)
        label.setText(f"⏱ {m:02d}:{s:02d}")

    def _fade_out_label(self, label):
        eff = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity")
        anim.setDuration(1500)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        label._anim = anim

    def _hash_file(self, path):
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _vt_lookup(self, sha256):
        headers = {"accept": "application/json", "x-apikey": VT_API_KEY}
        url = f"https://www.virustotal.com/api/v3/files/{sha256}"
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json().get("data")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return None

    def closeEvent(self, event):
        """Clean shutdown when page is closed."""
        # Stop all active processes
        if self._active_proc and self._active_proc.poll() is None:
            try:
                self._active_proc.terminate()
                self._active_proc.wait(timeout=2)
            except:
                try:
                    self._active_proc.kill()
                except:
                    pass
        
        # Stop timers
        if self._active_timer and self._active_timer.isActive():
            self._active_timer.stop()
        
        # Close active log window
        if self._active_log:
            try:
                self._active_log.close()
            except:
                pass
        
        # Wait for threads to finish (with timeout)
        for thread in list(self._active_threads):
            if thread.is_alive():
                # Threads are daemon, but give them a moment to cleanup
                thread.join(timeout=0.5)
        
        self._active_threads.clear()
        event.accept()