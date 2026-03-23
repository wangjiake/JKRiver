"""System info script for JKRiver system_info agent.

Usage: python3 scripts/system_info.py --target cpu|memory|disk|all

Uses built-in system commands — no third-party dependencies required.
psutil is used as an optional enhancement when available.
"""

import argparse
import platform
import subprocess
import sys


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, timeout=5, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def _cpu():
    try:
        import psutil
        pct = psutil.cpu_percent(interval=0.5)
        count = psutil.cpu_count(logical=True)
        freq = psutil.cpu_freq()
        freq_str = f"{freq.current:.0f} MHz" if freq else ""
        return f"CPU: {pct}% usage | {count} logical cores" + (f" | {freq_str}" if freq_str else "")
    except ImportError:
        pass

    os_name = platform.system()
    if os_name == "Darwin":
        cores = _run(["sysctl", "-n", "hw.logicalcpu"])
        load = _run(["sysctl", "-n", "vm.loadavg"])
        return f"CPU: {cores} logical cores | Load avg: {load}"
    elif os_name == "Linux":
        cores = _run(["nproc"])
        load = _run(["cat", "/proc/loadavg"])
        return f"CPU: {cores} logical cores | Load avg: {load.split()[:3]}"
    return "CPU: info unavailable"


def _memory():
    try:
        import psutil
        vm = psutil.virtual_memory()
        total = vm.total / (1024 ** 3)
        used = vm.used / (1024 ** 3)
        avail = vm.available / (1024 ** 3)
        return f"Memory: {used:.1f}/{total:.1f} GB used ({vm.percent}%) | {avail:.1f} GB free"
    except ImportError:
        pass

    os_name = platform.system()
    if os_name == "Darwin":
        total_bytes = int(_run(["sysctl", "-n", "hw.memsize"]) or "0")
        total_gb = total_bytes / (1024 ** 3)
        vm_stat = _run(["vm_stat"])
        page_size = 16384
        free_pages = 0
        for line in vm_stat.splitlines():
            if "Pages free" in line:
                free_pages = int(line.split(":")[1].strip().rstrip("."))
                break
        free_gb = (free_pages * page_size) / (1024 ** 3)
        used_gb = total_gb - free_gb
        return f"Memory: {used_gb:.1f}/{total_gb:.1f} GB used | {free_gb:.1f} GB free"
    elif os_name == "Linux":
        out = _run(["cat", "/proc/meminfo"])
        info = {}
        for line in out.splitlines():
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()
        total_kb = int(info.get("MemTotal", "0").split()[0])
        avail_kb = int(info.get("MemAvailable", "0").split()[0])
        used_kb = total_kb - avail_kb
        return (f"Memory: {used_kb/1024/1024:.1f}/{total_kb/1024/1024:.1f} GB used "
                f"| {avail_kb/1024/1024:.1f} GB free")
    return "Memory: info unavailable"


def _disk():
    try:
        import psutil
        parts = []
        for dp in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(dp.mountpoint)
                total = usage.total / (1024 ** 3)
                used = usage.used / (1024 ** 3)
                free = usage.free / (1024 ** 3)
                parts.append(f"  {dp.mountpoint}: {used:.1f}/{total:.1f} GB ({usage.percent}% used)")
            except PermissionError:
                continue
        return "Disk:\n" + "\n".join(parts) if parts else "Disk: no info"
    except ImportError:
        pass

    out = _run(["df", "-h", "-l"])
    lines = out.splitlines()
    if len(lines) <= 1:
        return "Disk: info unavailable"
    header = lines[0]
    rows = [header] + [l for l in lines[1:] if not any(
        x in l for x in ["devfs", "map ", "ditto", "xarts", "Preboot", "Update", "iSCPreboot", "Hardware", "VM"]
    )]
    return "Disk:\n" + "\n".join(rows)


def _all():
    lines = [
        f"OS: {platform.system()} {platform.release()} ({platform.machine()}) | Python {sys.version.split()[0]}",
        _cpu(),
        _memory(),
        _disk(),
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["cpu", "memory", "disk", "all"], default="all")
    args = parser.parse_args()

    result = {
        "cpu": _cpu,
        "memory": _memory,
        "disk": _disk,
        "all": _all,
    }[args.target]()

    print(result)


if __name__ == "__main__":
    main()
