from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import psutil

from app.infra.settings import Settings, get_settings

SnapshotDict = dict[str, int | float | str | None]
_CPU_SAMPLE_CACHE: dict[str, tuple[float, float]] = {}


@dataclass(slots=True)
class ResourceSnapshot:
    status: str
    rss_bytes: int
    unique_bytes: int | None
    vms_bytes: int
    cpu_seconds: float
    cpu_percent: float
    process_count: int

    def to_dict(self) -> SnapshotDict:
        return {
            "status": self.status,
            "rss_bytes": self.rss_bytes,
            "unique_bytes": self.unique_bytes,
            "vms_bytes": self.vms_bytes,
            "cpu_seconds": round(self.cpu_seconds, 3),
            "cpu_percent": round(self.cpu_percent, 1),
            "process_count": self.process_count,
        }


def _safe_path(value: str | None) -> Path | None:
    if not value:
        return None
    try:
        return Path(value).resolve()
    except (OSError, RuntimeError):
        return None


def _is_under(path: Path | None, root: Path) -> bool:
    if path is None:
        return False
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_cmdline(process: psutil.Process) -> str:
    try:
        return " ".join(process.cmdline()).lower()
    except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
        return ""


def _safe_cwd(process: psutil.Process) -> Path | None:
    try:
        return _safe_path(process.cwd())
    except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess, FileNotFoundError):
        return None


def _safe_name(process: psutil.Process) -> str:
    try:
        return process.name().lower()
    except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
        return ""


def _calculate_cpu_percent(cache_key: str, cpu_seconds: float) -> float:
    now = time.monotonic()
    previous = _CPU_SAMPLE_CACHE.get(cache_key)
    _CPU_SAMPLE_CACHE[cache_key] = (now, cpu_seconds)

    if previous is None:
        return 0.0

    previous_time, previous_cpu = previous
    wall_delta = now - previous_time
    cpu_delta = cpu_seconds - previous_cpu
    if wall_delta <= 0 or cpu_delta <= 0:
        return 0.0
    return (cpu_delta / wall_delta) * 100.0


def _snapshot_from_pids(pids: Iterable[int], cache_key: str) -> ResourceSnapshot:
    rss_bytes = 0
    unique_bytes = 0
    unique_available = True
    vms_bytes = 0
    cpu_seconds = 0.0
    process_count = 0

    for pid in sorted(set(pids)):
        try:
            process = psutil.Process(pid)
            memory_info = process.memory_info()
            memory_full_info = process.memory_full_info()
            cpu_times = process.cpu_times()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        rss_bytes += int(memory_info.rss)
        process_unique = getattr(memory_full_info, "uss", None) or getattr(
            memory_full_info, "pss", None
        )
        if process_unique is None:
            unique_available = False
        else:
            unique_bytes += int(process_unique)
        vms_bytes += int(memory_info.vms)
        cpu_seconds += float(cpu_times.user + cpu_times.system)
        process_count += 1

    status = "available" if process_count > 0 else "unavailable"
    cpu_percent = _calculate_cpu_percent(cache_key, cpu_seconds) if process_count > 0 else 0.0
    return ResourceSnapshot(
        status=status,
        rss_bytes=rss_bytes,
        unique_bytes=unique_bytes if unique_available and process_count > 0 else None,
        vms_bytes=vms_bytes,
        cpu_seconds=cpu_seconds,
        cpu_percent=cpu_percent,
        process_count=process_count,
    )


def _collect_process_tree(root_pid: int) -> set[int]:
    pids: set[int] = set()
    try:
        root = psutil.Process(root_pid)
        pids.add(root.pid)
        for child in root.children(recursive=True):
            pids.add(child.pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return set()
    return pids


def _collect_matching_pids(matcher: Callable[[psutil.Process], bool]) -> set[int]:
    pids: set[int] = set()
    for process in psutil.process_iter(["pid"]):
        try:
            if matcher(process):
                pids.add(process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return pids


def _frontend_matcher(frontend_root: Path) -> Callable[[psutil.Process], bool]:
    def matcher(process: psutil.Process) -> bool:
        cwd = _safe_cwd(process)
        cmdline = _safe_cmdline(process)
        name = _safe_name(process)
        in_frontend = _is_under(cwd, frontend_root) or str(frontend_root).lower() in cmdline
        runtime_match = any(
            token in cmdline for token in ("next", "next-server", "npm run dev")
        ) or name in {
            "node",
            "npm",
        }
        return in_frontend and runtime_match

    return matcher


def _postgres_matcher(db_port: int | None) -> Callable[[psutil.Process], bool]:
    def matcher(process: psutil.Process) -> bool:
        name = _safe_name(process)
        cmdline = _safe_cmdline(process)
        if "postgres" not in name and "postgres" not in cmdline:
            return False
        if db_port is None:
            return True
        try:
            for connection in process.net_connections(kind="inet"):
                if connection.laddr and connection.laddr.port == db_port:
                    return True
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            return "postgres" in name
        return "postgres" in name

    return matcher


def _parse_db_port(database_url: str) -> int | None:
    normalized = database_url
    if "+psycopg" in normalized:
        normalized = normalized.replace("+psycopg", "", 1)
    parsed = urlparse(normalized)
    return parsed.port


def get_system_overview_payload(settings: Settings | None = None) -> dict[str, object]:
    settings = settings or get_settings()
    backend_pids = _collect_process_tree(os.getpid())
    frontend_pids = _collect_matching_pids(_frontend_matcher(settings.project_root / "frontend"))
    postgres_pids = _collect_matching_pids(_postgres_matcher(_parse_db_port(settings.database_url)))

    backend = _snapshot_from_pids(backend_pids, "backend")
    frontend = _snapshot_from_pids(frontend_pids - backend_pids, "frontend")
    postgres = _snapshot_from_pids(postgres_pids - backend_pids - frontend_pids, "postgres")
    total = _snapshot_from_pids(backend_pids | frontend_pids | postgres_pids, "total")

    return {
        "collected_at": int(time.time() * 1000),
        "components": {
            "backend": backend.to_dict(),
            "frontend": frontend.to_dict(),
            "postgres": postgres.to_dict(),
            "total": total.to_dict(),
        },
    }
