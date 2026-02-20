import psutil
import time
import shutil


class MetricsCollector:
    def __init__(self):
        self.start_time = None
        self.end_time = None

    # -----------------------------
    # Build Time Tracking
    # -----------------------------
    def start_timer(self):
        self.start_time = time.time()

    def stop_timer(self):
        self.end_time = time.time()

    def get_build_time(self):
        if self.start_time and self.end_time:
            return round(self.end_time - self.start_time, 2)
        return 0

    # -----------------------------
    # System Metrics
    # -----------------------------
    @staticmethod
    def get_cpu_usage():
        return round(psutil.cpu_percent(interval=1), 2)

    @staticmethod
    def get_memory_usage():
        memory = psutil.virtual_memory()
        return round(memory.percent, 2)

    @staticmethod
    def get_disk_usage():
        total, used, free = shutil.disk_usage("/")
        return round((used / total) * 100, 2)

    # -----------------------------
    # Combined Metrics
    # -----------------------------
    def collect_metrics(self):
        return {
            "cpu": self.get_cpu_usage(),
            "memory": self.get_memory_usage(),
            "disk": self.get_disk_usage(),
            "build_time": self.get_build_time()
        }