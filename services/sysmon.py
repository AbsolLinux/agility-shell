import os
from fabric.core.service import Service, Property, Signal
from gi.repository import GLib

class SysMonService(Service):
    @Signal
    def changed(self) -> None: ...

    @Property(float, "readable", default_value=0.0)
    def cpu_usage(self) -> float:
        return self._cpu_usage

    @Property(float, "readable", default_value=0.0)
    def mem_usage(self) -> float:
        return self._mem_usage

    @Property(str, "readable", default_value="0 MB")
    def mem_used_str(self) -> str:
        return self._mem_used_str

    @Property(str, "readable", default_value="0 MB")
    def mem_total_str(self) -> str:
        return self._mem_total_str

    def __init__(self, interval_ms: int = 2000, **kwargs):
        super().__init__(**kwargs)
        self._cpu_usage = 0.0
        self._mem_usage = 0.0
        self._mem_used_str = "0 MB"
        self._mem_total_str = "0 MB"
        self._last_cpu_total = 0
        self._last_cpu_idle = 0

        self._update()
        GLib.timeout_add(interval_ms, self._poll)

    def _poll(self) -> bool:
        self._update()
        return True

    def _update(self):
        # Update CPU
        try:
            with open("/proc/stat", "r") as f:
                line = f.readline()
                parts = [float(x) for x in line.split()[1:8]]
                idle = parts[3] + parts[4]
                total = sum(parts)

                if self._last_cpu_total > 0:
                    diff_total = total - self._last_cpu_total
                    diff_idle = idle - self._last_cpu_idle
                    if diff_total > 0:
                        self._cpu_usage = max(0.0, min(100.0, ((diff_total - diff_idle) / diff_total) * 100.0))
                self._last_cpu_total = total
                self._last_cpu_idle = idle
        except Exception:
            pass

        # Update Memory
        try:
            mem_info = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        mem_info[k] = float(v)

            total_kb = mem_info.get("MemTotal", 1.0)
            avail_kb = mem_info.get("MemAvailable", mem_info.get("MemFree", 0.0))
            used_kb = total_kb - avail_kb
            self._mem_usage = max(0.0, min(100.0, (used_kb / total_kb) * 100.0))

            used_gb = used_kb / (1024 * 1024)
            total_gb = total_kb / (1024 * 1024)
            if total_gb >= 1.0:
                self._mem_used_str = f"{used_gb:.1f} GB"
                self._mem_total_str = f"{total_gb:.1f} GB"
            else:
                self._mem_used_str = f"{int(used_kb / 1024)} MB"
                self._mem_total_str = f"{int(total_kb / 1024)} MB"
        except Exception:
            pass

        self.notify("cpu-usage")
        self.notify("mem-usage")
        self.notify("mem-used-str")
        self.notify("mem-total-str")
        self.emit("changed")
