import psutil
import GPUtil
import platform
import cpuinfo
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QFrame
from PySide6.QtCore import Qt, QTimer


class HardwarePage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        # Header
        title = QLabel("⚙️ Hardware Diagnostics")
        title.setObjectName("title")
        subtitle = QLabel("Monitor live system performance and health overview")
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # --- Create stat cards ---
        self.cpu_card, self.cpu_value, self.cpu_bar = self.create_stat_card("CPU", "")
        self.mem_card, self.mem_value, self.mem_bar = self.create_stat_card("Memory", "")
        self.disk_card, self.disk_value, self.disk_bar = self.create_stat_card("Disk", "")
        self.gpu_cards = []

        layout.addWidget(self.cpu_card)
        layout.addWidget(self.mem_card)
        layout.addWidget(self.disk_card)

        # Detect GPUs
        gpus = GPUtil.getGPUs()
        if gpus:
            for i, gpu in enumerate(gpus):
                card, value_lbl, bar = self.create_stat_card(f"GPU {i}: {gpu.name}", "")
                layout.addWidget(card)
                self.gpu_cards.append((gpu.id, value_lbl, bar))
        else:
            card, value_lbl, bar = self.create_stat_card("GPU", "N/A")
            layout.addWidget(card)
            self.gpu_cards.append((None, value_lbl, bar))

        layout.addStretch()
        self.setLayout(layout)

        # Update every 1 second
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)

        self.update_stats()  # initial populate

    # ---- Card Template ----
    def create_stat_card(self, label, value_text):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
            }
            QLabel { color: #e8eef6; }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title_lbl = QLabel(label)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        value_lbl = QLabel(value_text)
        value_lbl.setStyleSheet("font-size: 18px; color: #cfd7ff; font-weight: 600;")

        progress = QProgressBar()
        progress.setTextVisible(False)
        progress.setFixedHeight(8)
        progress.setRange(0, 100)
        progress.setStyleSheet("""
            QProgressBar {
                background: #11151f;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: #6e8bff;
                border-radius: 4px;
            }
        """)

        layout.addWidget(title_lbl)
        layout.addWidget(value_lbl)
        layout.addWidget(progress)
        return card, value_lbl, progress

    # ---- Live Updater ----
    def update_stats(self):
        # CPU
        try:
            cpu_usage = psutil.cpu_percent(interval=None)
            freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0
            temp = "N/A"
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if "coretemp" in temps:
                    cpu_temp_vals = [t.current for t in temps["coretemp"]]
                    temp = f"{sum(cpu_temp_vals)/len(cpu_temp_vals):.1f}°C"
            cpu_model = cpuinfo.get_cpu_info().get("brand_raw", platform.processor())
            self.cpu_value.setText(f"{cpu_model}\n{cpu_usage:.0f}%  •  {freq/1000:.2f} GHz  •  {temp}")
            self.cpu_bar.setValue(int(cpu_usage))
        except Exception as e:
            self.cpu_value.setText(f"Error reading CPU: {e}")

        # Memory
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024 ** 3)
        total_gb = mem.total / (1024 ** 3)
        mem_usage = mem.percent
        self.mem_value.setText(f"{used_gb:.1f} GB / {total_gb:.1f} GB  ({mem_usage:.0f}%)")
        self.mem_bar.setValue(int(mem_usage))

        # Disk
        disk = psutil.disk_usage('/')
        disk_usage = disk.percent
        io = psutil.disk_io_counters()
        read_mb = io.read_bytes / (1024 ** 2)
        write_mb = io.write_bytes / (1024 ** 2)
        self.disk_value.setText(f"{disk_usage:.0f}% • Read: {read_mb:.0f} MB  Write: {write_mb:.0f} MB")
        self.disk_bar.setValue(int(disk_usage))

        # GPU(s)
        try:
            gpus = GPUtil.getGPUs()
            for idx, (gpu_id, value_lbl, bar) in enumerate(self.gpu_cards):
                if idx < len(gpus):
                    gpu = gpus[idx]
                    load = gpu.load * 100
                    mem_used = gpu.memoryUsed
                    mem_total = gpu.memoryTotal
                    temp = f"{gpu.temperature}°C" if gpu.temperature else "N/A"
                    value_lbl.setText(f"{load:.0f}% • {mem_used:.1f}/{mem_total:.1f} GB VRAM • {temp}")
                    bar.setValue(int(load))
                else:
                    value_lbl.setText("No GPU detected")
                    bar.setValue(0)
        except Exception:
            for _, value_lbl, bar in self.gpu_cards:
                value_lbl.setText("GPU data unavailable")
                bar.setValue(0)
