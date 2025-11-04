# ui/clean_tune_page.py

import os
import re
import time
import hashlib
import threading
import subprocess
from datetime import datetime

import requests
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QPropertyAnimation, QCoreApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QTextEdit, QDialog, QFileDialog,
    QHBoxLayout, QCheckBox, QDialogButtonBox, QMessageBox,
    QGraphicsOpacityEffect, QApplication
)

# --------------------- VirusTotal API Key ---------------------
# Skipping dotenv — key is hardcoded and always available.
VT_API_KEY = "2bfe6972b6f0cfe9dd9b067fee7b1b5b0b7f6f1fe765c88d1750faf8333a7a9a"


# If you prefer using environment variable, set VT_API_KEY in Windows
# Else, this fallback will always work with your key below.
VT_API_KEY = os.getenv("VT_API_KEY", "").strip()
if not VT_API_KEY:
    VT_API_KEY = "2bfe6972b6f0cfe9dd9b067fee7b1b5b0b7f6f1fe765c88d1750faf8333a7a9a"


# ----------------------------- Log Window -----------------------------
class LogWindow(QDialog):
    closed = Signal()

    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(750, 480)

        v = QVBoxLayout(self)
        self.text = QTextEdit(readOnly=True)
        v.addWidget(self.text)

        self.timer_label = QLabel("⏱ Elapsed Time: 0s")
        self.timer_label.setStyleSheet("color:#9eb3ff; font-size:13px;")
        v.addWidget(self.timer_label)

        self._start = datetime.now()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        secs = int((datetime.now() - self._start).total_seconds())
        self.timer_label.setText(f"⏱ Elapsed Time: {secs}s")

    def append(self, s: str):
        if not s:
            return
        self.text.append(s)
        sb = self.text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def stop_timer(self):
        if self._timer.isActive():
            self._timer.stop()

    def closeEvent(self, e):
        self.stop_timer()
        self.closed.emit()
        super().closeEvent(e)


# ----------------------------- Signals -----------------------------
class WorkerSignals(QObject):
    progress = Signal(int)
    message = Signal(str)
    done = Signal(bool, str)


# ----------------------------- Cleanup Options -----------------------------
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

        v.addSpacing(6)
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


# ----------------------------- Main Page -----------------------------
class CleanTunePage(QWidget):
    def __init__(self):
        super().__init__()
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
                "ps": "sfc /scannow"
            },
            "DISM Repair": {
                "desc": "Repairs Windows system image",
                "ps": "DISM /Online /Cleanup-Image /RestoreHealth"
            },
            "Cleanup Temp Files": {
                "desc": "Removes temporary & update caches (optional browser caches)",
                "ps": None
            },
            "SmartScan (VirusTotal)": {
                "desc": "Hash-check files with VirusTotal (Shift = choose folder)",
                "ps": None
            },
        }

        self.progress_bars = {}
        self.time_labels = {}
        self._active_proc = None
        self._active_timer = None
        self._active_log = None

        r = c = 0
        for name, meta in self.tools.items():
            card, pbar, tlabel = self._make_card(name, meta["desc"])
            self.progress_bars[name] = pbar
            self.time_labels[name] = tlabel
            grid.addWidget(card, r, c)
            c = (c + 1) % 2
            if c == 0:
                r += 1

        root.addLayout(grid)

    # ------------------------- UI card -------------------------
    def _make_card(self, title, desc):
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background:#1b2230; border:1px solid #2b3548; border-radius:12px; }
            QLabel { color:#e8eef6; }
        """)
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        t = QLabel(title)
        t.setStyleSheet("font-size:16px; font-weight:600; color:#fff;")
        d = QLabel(desc)
        d.setStyleSheet("color:#cfd7ff; font-size:13px;")

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
        tl.setStyleSheet("color:#8aa0ff; font-size:12px; font-style:italic;")

        row = QHBoxLayout()
        row.addWidget(bar)
        row.addWidget(tl)
        row.setStretch(0, 5)
        row.setStretch(1, 1)

        btn = QPushButton("▶ Run Tool")
        btn.setStyleSheet("""
            QPushButton { background:#6e8bff; color:white; border:none; border-radius:6px; padding:8px; font-weight:600; }
            QPushButton:hover { background:#869eff; }
        """)
        btn.clicked.connect(lambda _, n=title: self._start_tool(n))

        v.addWidget(t)
        v.addWidget(d)
        v.addLayout(row)
        v.addStretch()
        v.addWidget(btn)
        return card, bar, tl

    # ------------------------- Start tool -------------------------
    def _start_tool(self, tool_name: str):
        pbar = self.progress_bars[tool_name]
        tlab = self.time_labels[tool_name]
        pbar.setValue(0)
        tlab.setText("⏱ 00:00")

        log = LogWindow(tool_name)
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
                except Exception:
                    pass
            if card_timer.isActive():
                card_timer.stop()
            tlab.setText("⏱ canceled")

        log.closed.connect(stop_running)

        sig = WorkerSignals()
        sig.progress.connect(pbar.setValue)
        sig.message.connect(log.append)
        sig.done.connect(lambda ok, msg: self._finish(ok, msg, tool_name, log, card_timer, tlab))

        if tool_name == "SmartScan (VirusTotal)":
            folder = None
            if (QApplication.keyboardModifiers() & Qt.ShiftModifier):
                folder = QFileDialog.getExistingDirectory(self, "Select Folder to Scan")
                if not folder:
                    log.append("SmartScan cancelled.")
                    card_timer.stop()
                    return
            else:
                folder = os.path.join(os.path.expanduser("~"), "Downloads")
            threading.Thread(target=self._smartscan_worker, args=(folder, sig), daemon=True).start()

        elif tool_name == "Cleanup Temp Files":
            dlg = AdvancedCleanupDialog(self)
            if dlg.exec() != QDialog.Accepted:
                log.append("Cleanup cancelled.")
                card_timer.stop()
                return
            opts = dlg.selections()
            threading.Thread(target=self._cleanup_worker, args=(opts, sig), daemon=True).start()

        else:
            ps_cmd = self.tools[tool_name]["ps"]
            threading.Thread(target=self._powershell_worker, args=(ps_cmd, sig), daemon=True).start()

    # ------------------------- PowerShell Worker -------------------------
    def _powershell_worker(self, inner_cmd: str, sig: WorkerSignals):
        script = (
            "$ProgressPreference='SilentlyContinue'; "
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
            "chcp 65001 > $null; "
            f"{inner_cmd}"
        )

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            startupinfo=si,
            creationflags=flags,
            shell=False
        )
        self._active_proc = proc

        percent_pat = re.compile(r'(\d{1,3})(?:\.\d+)?\s*%')
        for line in proc.stdout:
            if not line:
                continue
            clean = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", line).strip()
            if not clean:
                continue
            sig.message.emit(clean)
            m = percent_pat.search(clean)
            if m:
                pct = max(0, min(100, int(float(m.group(1)))))
                sig.progress.emit(pct)
        proc.wait()
        sig.done.emit(proc.returncode == 0, f"Finished with code {proc.returncode}")

    # ------------------------- Cleanup Worker -------------------------
    def _cleanup_worker(self, opts: dict, sig: WorkerSignals):
        lines = [
            'Write-Output "Starting Cleanup...";',
            'Write-Output "Deleting %TEMP% files..."; if (Test-Path $env:TEMP) { Remove-Item "$env:TEMP\\*" -Recurse -Force -ErrorAction SilentlyContinue }',
            'Write-Output "Deleting Windows Prefetch..."; if (Test-Path "$env:SystemRoot\\Prefetch") { Remove-Item "$env:SystemRoot\\Prefetch\\*" -Recurse -Force -ErrorAction SilentlyContinue }',
            'Write-Output "Deleting Update cache..."; if (Test-Path "$env:SystemRoot\\SoftwareDistribution\\Download") { Remove-Item "$env:SystemRoot\\SoftwareDistribution\\Download\\*" -Recurse -Force -ErrorAction SilentlyContinue }'
        ]
        if opts.get("chrome"):
            lines.append('Write-Output "Clearing Chrome cache...";')
        if opts.get("edge"):
            lines.append('Write-Output "Clearing Edge cache...";')
        if opts.get("firefox"):
            lines.append('Write-Output "Clearing Firefox cache...";')
        lines.append('Write-Output "Cleanup complete.";')

        script = (
            "$ProgressPreference='SilentlyContinue'; "
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
            "chcp 65001 > $null; " + " ".join(lines)
        )

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            startupinfo=si,
            creationflags=flags,
            shell=False
        )
        self._active_proc = proc

        for line in proc.stdout:
            clean = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", line).strip()
            if clean:
                sig.message.emit(clean)
        proc.wait()
        sig.done.emit(proc.returncode == 0, f"Cleanup finished with code {proc.returncode}")

    # ------------------------- SmartScan -------------------------
    def _smartscan_worker(self, folder: str, sig: WorkerSignals):
        if not os.path.isdir(folder):
            sig.done.emit(False, "Folder not found.")
            return
        files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        if not files:
            sig.done.emit(False, "No files to scan.")
            return
        if not VT_API_KEY:
            sig.message.emit("⚠️ VirusTotal key not set. Set VT_API_KEY env var to enable lookups.")
            sig.done.emit(False, "SmartScan aborted.")
            return

        infected = 0
        for i, path in enumerate(files, 1):
            name = os.path.basename(path)
            sig.message.emit(f"Hashing {name}...")
            h = self._hash_file(path)
            sig.message.emit(f"Querying VT for {name}...")
            try:
                data = self._vt_lookup(h)
                if data:
                    stats = data.get("attributes", {}).get("last_analysis_stats", {})
                    bad = int(stats.get("malicious", 0) or 0)
                    if bad > 0:
                        infected += 1
                        sig.message.emit(f"⚠️ {name}: flagged by {bad} engines.")
                    else:
                        sig.message.emit(f"✅ {name}: clean.")
                else:
                    sig.message.emit(f"ℹ️ {name}: not found on VT.")
            except Exception as e:
                sig.message.emit(f"Error checking {name}: {e}")
            sig.progress.emit(int(i * 100 / len(files)))
            QCoreApplication.processEvents()
            time.sleep(0.3)
        msg = f"{infected} file(s) flagged." if infected else "All files clean ✅"
        sig.done.emit(True, msg)

    # ------------------------- Helpers -------------------------
    def _finish(self, ok, msg, tool, log, card_timer, tlab):
        if card_timer.isActive():
            card_timer.stop()
        log.stop_timer()
        log.append("\n" + msg)
        log.append("\n" + "-" * 40)
        if ok:
            self.progress_bars[tool].setValue(100)
            QMessageBox.information(self, "Task Complete", msg)
        else:
            QMessageBox.warning(self, "Task Failed", msg)
        self._fade_out_label(tlab)
        self._active_proc = None
        self._active_timer = None
        self._active_log = None

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
            for chunk in iter(lambda: f.read(1 << 16), b""):
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
