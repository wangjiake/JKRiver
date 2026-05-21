"""Stats endpoints — system resources and token usage."""

from fastapi import APIRouter, Request

from agent.core.identity import DEFAULT_OWNER_ID
from agent.routers import _state

router = APIRouter(tags=["stats"])

_net_last: dict = {}


@router.get("/api/system/stats")
async def system_stats():
    try:
        import psutil, time
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        disk_free_gb = disk.free / 1024 ** 3
        net = psutil.net_io_counters()
        now = time.monotonic()
        upload_bps = download_bps = 0.0
        if _net_last:
            dt = now - _net_last["time"]
            if dt > 0:
                upload_bps = (net.bytes_sent - _net_last["bytes_sent"]) / dt
                download_bps = (net.bytes_recv - _net_last["bytes_recv"]) / dt
        _net_last.update({"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "time": now})
        return {
            "cpu": round(cpu, 1),
            "mem": round(mem.percent, 1),
            "disk_pct": round(disk.percent, 1),
            "disk_free_gb": round(disk_free_gb, 1),
            "upload_bps": round(upload_bps),
            "download_bps": round(download_bps),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/token-usage")
async def token_usage_stats(request: Request):
    try:
        from agent.storage.token_usage import get_stats
        timezone = _state._config.get("timezone", "UTC") if _state._config else "UTC"
        owner_id = getattr(request.state, "owner_id", DEFAULT_OWNER_ID)
        return get_stats(timezone, owner_id=owner_id)
    except Exception as e:
        return {"error": str(e)}
