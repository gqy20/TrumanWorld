#!/usr/bin/env python3
"""录制 Truman World run demo 视频。

创建（可选）一个新 run，开启 scheduler 自动 tick，用 Playwright headless
chromium 访问前端 run 页面（默认 ``/runs/{id}/world``，这是 ``/runs/{id}``
重定向后的实际页面），依次录制导演与舞台视图，再用 ffmpeg 同步转 mp4。

可复用：所有路径/参数都从命令行或环境变量读取，便于不同 run、不同场景复用。

依赖：
  - backend env 已装 ``playwright`` Python 包
  - ``uv run --with playwright python scripts/record_run_demo.py`` 也能跑
  - 系统已装 ``ffmpeg`` 用于 webm → mp4
  - backend 在 ``--api-base`` 监听、frontend 在 ``--web-base`` 监听

示例：
  # 创建新 run 并录 10 分钟（默认 campus_world）
  uv run --project backend python backend/scripts/record_run_demo.py \\
      --create-run --name "campus demo 2026-08-04" \\
      --director-seconds 300 --stage-seconds 300

  # 复用已有 run
  uv run --project backend python backend/scripts/record_run_demo.py \\
      --run-id 49b939e4-41a5-4f08-ae99-0cfa1a0008a1 \\
      --director-seconds 300 --stage-seconds 300
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_API_BASE = "http://127.0.0.1:18080/api"
DEFAULT_WEB_BASE = "http://127.0.0.1:13000"
DEFAULT_SCENARIO = "campus_world"
DEFAULT_VIEWPORT = (1440, 900)
DEFAULT_RELOAD_INTERVAL = 60.0  # 秒：兜底刷新一次页面，确保前端拿到最新数据
DEFAULT_OUTPUT_ROOT = Path("recordings")


# ponytail: stdlib only（urllib + json），不引入 httpx/requests 这类依赖。
def _request_json(
    method: str, url: str, payload: dict | None = None, timeout: float = 30.0
) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {body}") from exc


def healthcheck(api_base: str) -> None:
    _request_json("GET", f"{api_base}/health")


@dataclass
class CreatedRun:
    id: str
    name: str
    scenario_type: str
    tick_minutes: int


def create_run(
    api_base: str, name: str, scenario: str, tick_minutes: int, seed_demo: bool
) -> CreatedRun:
    payload = {
        "name": name,
        "scenario_type": scenario,
        "seed_demo": seed_demo,
        "auto_start": True,  # 一并把 scheduler 起来，省一步
        "tick_minutes": tick_minutes,
    }
    data = _request_json("POST", f"{api_base}/runs", payload, timeout=60)
    return CreatedRun(
        id=data["id"],
        name=data["name"],
        scenario_type=data.get("scenario_type", scenario),
        tick_minutes=data.get("tick_minutes", tick_minutes),
    )


def start_run(api_base: str, run_id: str) -> None:
    _request_json("POST", f"{api_base}/runs/{run_id}/start", timeout=60)


def run_status(api_base: str, run_id: str) -> dict:
    return _request_json("GET", f"{api_base}/runs/{run_id}")


def _timestamp_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _ffmpeg_to_mp4(webm: Path, mp4: Path) -> None:
    if shutil.which("ffmpeg") is None:
        print(f"[warn] ffmpeg 不在 PATH，跳过转 mp4；原始 webm: {webm}", file=sys.stderr)
        return
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(webm),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",  # 静音
        str(mp4),
    ]
    print(f"[ffmpeg] {shlex.join(cmd)}")
    subprocess.run(cmd, check=True)


def _ffmpeg_concat(seg_mp4s: list[Path], out_mp4: Path) -> None:
    # ponytail: 两段同 codec mp4，用 concat demuxer 直接拼接。
    list_file = out_mp4.parent / "_concat.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in seg_mp4s) + "\n",
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(out_mp4),
    ]
    print(f"[ffmpeg-concat] {shlex.join(cmd)}")
    subprocess.run(cmd, check=True)
    list_file.unlink(missing_ok=True)


def record(
    *,
    web_base: str,
    run_id: str,
    out_dir: Path,
    duration: float,
    viewport: tuple[int, int],
    reload_interval: float,
    director_seconds: float,
    stage_seconds: float,
    device_scale_factor: float,
) -> Path:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError as exc:  # ponytail: 一次性错误信息，不污染顶层 import。
        raise SystemExit(
            "playwright Python 包未安装。运行：uv pip install --project backend playwright\n"
            "或：uv run --with playwright python backend/scripts/record_run_demo.py ..."
        ) from exc

    target_url = f"{web_base.rstrip('/')}/runs/{run_id}/world"
    out_dir.mkdir(parents=True, exist_ok=True)
    webm_path = out_dir / "demo.webm"
    log_path = out_dir / "recording.log"

    width, height = viewport
    log_lines: list[str] = []
    started = time.time()

    def log(msg: str) -> None:
        line = f"[{time.time() - started:7.2f}s] {msg}"
        print(line, flush=True)
        log_lines.append(line)

    log(f"开始录制：{target_url}")
    log(
        f"viewport: {width}x{height}  duration: {duration:.0f}s  reload_interval: {reload_interval:.0f}s"
    )
    log(f"segments: director={director_seconds:.0f}s + stage={stage_seconds:.0f}s")
    log(f"输出目录: {out_dir}")

    with sync_playwright() as pw:
        # ponytail: 用系统 Chrome（已装），免下载 playwright 自带 chromium；
        # 若环境没有 Chrome，channel=chrome 启动会失败，提示用户装浏览器。
        browser = pw.chromium.launch(headless=True, channel="chrome")
        record_w = max(1, round(width * device_scale_factor))
        record_h = max(1, round(height * device_scale_factor))
        context = browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=device_scale_factor,
            record_video_dir=str(out_dir),
            record_video_size={"width": record_w, "height": record_h},
        )
        page = context.new_page()
        # ponytail: console 落日志，便于剪辑时回放定位异常时刻。
        page.on("console", lambda m: log(f"[console.{m.type}] {m.text[:200]}"))
        page.on("pageerror", lambda e: log(f"[pageerror] {e}"))

        log(f"goto {target_url}")
        page.goto(target_url, wait_until="domcontentloaded", timeout=60_000)
        # 等首屏骨架渲染出来（world view 通常是 canvas / WebGL）。
        page.wait_for_timeout(3000)

        # segments 时间表：[view_name, seconds]，按序录制。
        segments: list[tuple[str, float]] = []
        if director_seconds > 0:
            segments.append(("director", director_seconds))
        if stage_seconds > 0:
            segments.append(("stage", stage_seconds))
        if not segments:
            raise SystemExit("director-seconds 和 stage-seconds 都是 0，没东西可录")

        # 计算每段结束时间点
        segment_ends: list[float] = []
        cursor = started
        for _, dur in segments:
            cursor += dur
            segment_ends.append(cursor)
        deadline = segment_ends[-1]
        next_reload = started + reload_interval

        def switch_to_view(view: str) -> None:
            # ponytail: 用 getByRole 找按钮，失败不阻塞录制（页面可能没有切换按钮）。
            # 4K 下 click 可能慢，timeout 给 10s 留余量。
            click_timeout = 10_000
            try:
                if view == "stage":
                    page.get_by_role("button", name="舞台视图").click(timeout=click_timeout)
                    page.wait_for_timeout(2000)  # 等 WebGL 初始化
                    # 切到 stage 后重置镜头，让 voxel 场景回到默认视角
                    try:
                        page.get_by_role("button", name="重置镜头").click(timeout=click_timeout)
                        page.wait_for_timeout(1500)
                    except Exception as exc:  # noqa: BLE001
                        log(f"  点「重置镜头」失败：{exc}")
                elif view == "director":
                    page.get_by_role("button", name="导演地图").click(timeout=click_timeout)
                    page.wait_for_timeout(1500)
                log(f"切换视图 -> {view}")
            except Exception as exc:  # noqa: BLE001
                log(f"切换视图 {view} 失败：{exc}")

        current_view: str | None = None
        seg_idx = 0
        while time.time() < deadline:
            now = time.time()
            # 推进 segment 索引
            while seg_idx < len(segments) and now >= segment_ends[seg_idx]:
                seg_idx += 1
            if seg_idx >= len(segments):
                break
            view_name, _ = segments[seg_idx]
            # 进入新 segment 时切换视图
            if current_view != view_name:
                switch_to_view(view_name)
                current_view = view_name

            if now >= next_reload:
                log("reload 页面（兜底刷新，触发前端重新拉数据）")
                try:
                    page.reload(wait_until="domcontentloaded", timeout=60_000)
                    page.wait_for_timeout(2000)
                    # reload 后视图会回到默认（director），需要重新切回当前 segment 的视图
                    if current_view is not None:
                        switch_to_view(current_view)
                except Exception as exc:  # noqa: BLE001
                    log(f"reload 失败：{exc}")
                next_reload = now + reload_interval
            try:
                status = run_status(DEFAULT_API_BASE, run_id)
                tick = status.get("current_tick", "?")
                elapsed = status.get("elapsed_seconds", "?")
                seg_progress = f"{now - (segment_ends[seg_idx - 1] if seg_idx > 0 else started):.0f}/{segments[seg_idx][1]:.0f}s"
                log(
                    f"run status tick={tick} elapsed={elapsed}s status={status.get('status')} | segment {seg_idx + 1}/{len(segments)} ({view_name}) {seg_progress}"
                )
            except Exception as exc:  # noqa: BLE001
                log(f"status 拉取失败：{exc}")
            page.wait_for_timeout(5000)  # 每 5s 打一次 status 日志

        log("录制结束，关闭浏览器并落盘 video")
        page.close()
        context.close()
        browser.close()

    # Playwright 把视频写到 record_video_dir 下，文件名形如
    # ``<random>.webm``。我们把它改名成 demo.webm。
    candidates = sorted(out_dir.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit(f"录制目录里没找到 webm：{out_dir}")
    src = candidates[0]
    if src.resolve() != webm_path.resolve():
        src.replace(webm_path)
    log(f"原始 webm: {webm_path}")

    # 落 recording.log
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    # ponytail: 同步转 mp4，便于剪辑（webm 保留作为原始素材）。
    _ffmpeg_to_mp4(webm_path, out_dir / "demo.mp4")
    return webm_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--api-base", default=DEFAULT_API_BASE, help="后端 API base（默认 %(default)s）")
    p.add_argument("--web-base", default=DEFAULT_WEB_BASE, help="前端 base（默认 %(default)s）")
    p.add_argument("--run-id", default=None, help="复用已有 run；与 --create-run 互斥")
    p.add_argument(
        "--create-run",
        action="store_true",
        help="创建一个新 run（campus_world 默认场景）",
    )
    p.add_argument(
        "--name", default=None, help="新建 run 的名称（默认 recordings/<tag>-<scenario>）"
    )
    p.add_argument("--scenario", default=DEFAULT_SCENARIO, help="scenario_type（默认 %(default)s）")
    p.add_argument(
        "--tick-minutes", type=int, default=5, help="每个 tick 多少分钟（默认 %(default)s）"
    )
    p.add_argument("--no-seed-demo", action="store_true", help="创建 run 时不灌演示数据")
    p.add_argument(
        "--reload-interval",
        type=float,
        default=DEFAULT_RELOAD_INTERVAL,
        help="兜底刷新页面间隔秒",
    )
    p.add_argument(
        "--viewport",
        default=f"{DEFAULT_VIEWPORT[0]}x{DEFAULT_VIEWPORT[1]}",
        help="录制视口，如 1440x900 或 3840x2160 (4K)",
    )
    p.add_argument(
        "--device-scale-factor",
        type=float,
        default=1.0,
        help="浏览器 device_scale_factor。>1 时视频像素 = viewport × scale，可在小 viewport 下得到更大视频清晰度",
    )
    p.add_argument(
        "--director-seconds",
        type=float,
        default=600.0,
        help="导演视图（svg 默认）录制秒数（默认 %(default)s = 10 分钟）",
    )
    p.add_argument(
        "--parallel",
        action="store_true",
        help="director/stage 两段并行录制（两个 Playwright 同时跑），总耗时 = max(两段时间)。--parallel 时 gpu/cpu 翻倍",
    )
    p.add_argument(
        "--stage-seconds",
        type=float,
        default=600.0,
        help="舞台视图（voxel）录制秒数（默认 %(default)s = 10 分钟）。总时长=director+stage",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="输出目录（默认 recordings/<run_id>_<timestamp>/）",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.run_id and args.create_run:
        print("--run-id 与 --create-run 互斥", file=sys.stderr)
        return 2
    if not args.run_id and not args.create_run:
        # ponytail: 不替用户选，强制二选一。
        print("必须传 --run-id 或 --create-run 之一", file=sys.stderr)
        return 2

    print(f"[init] healthcheck {args.api_base}")
    healthcheck(args.api_base)

    if args.create_run:
        tag = _timestamp_tag()
        name = args.name or f"{args.scenario} demo {tag}"
        print(f"[init] 创建 run：name={name!r} scenario={args.scenario}")
        created = create_run(
            api_base=args.api_base,
            name=name,
            scenario=args.scenario,
            tick_minutes=args.tick_minutes,
            seed_demo=not args.no_seed_demo,
        )
        print(f"[init] run 已创建：id={created.id}")
    else:
        print(f"[init] 复用 run：id={args.run_id}")
        status = run_status(args.api_base, args.run_id)
        # ponytail: 用户没说要 start，但我们让 run 一定是 running 状态。
        if status.get("status") in {"created", "paused"}:
            print(f"[init] run 当前 status={status.get('status')}，调用 /start 唤醒 scheduler")
            start_run(args.api_base, args.run_id)
        created = CreatedRun(
            id=args.run_id,
            name=status.get("name", args.run_id),
            scenario_type=status.get("scenario_type", args.scenario),
            tick_minutes=status.get("tick_minutes", args.tick_minutes),
        )

    out_dir = args.out or DEFAULT_OUTPUT_ROOT / f"{created.id}_{_timestamp_tag()}"
    out_dir = out_dir.resolve()
    print(f"[init] 输出目录：{out_dir}")

    w_str, h_str = args.viewport.lower().split("x", 1)
    viewport = (int(w_str), int(h_str))
    total_duration = args.director_seconds + args.stage_seconds
    mode_str = "并行" if args.parallel else "串行"
    print(
        f"[init] {mode_str}录制 导演 {args.director_seconds:.0f}s + 舞台 {args.stage_seconds:.0f}s"
        f"\n[init] viewport={viewport[0]}x{viewport[1]}  device_scale_factor={args.device_scale_factor}"
        f"  video={int(viewport[0] * args.device_scale_factor)}x{int(viewport[1] * args.device_scale_factor)}"
    )

    record_kwargs = dict(
        web_base=args.web_base,
        run_id=created.id,
        viewport=viewport,
        reload_interval=args.reload_interval,
        device_scale_factor=args.device_scale_factor,
    )

    if args.parallel:
        # ponytail: 两个 view 同时录到独立子目录，每段一份 mp4，不合并。
        seg_d_dir = out_dir / "seg_director"
        seg_s_dir = out_dir / "seg_stage"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_d = ex.submit(
                record,
                out_dir=seg_d_dir,
                duration=args.director_seconds,
                director_seconds=args.director_seconds,
                stage_seconds=0,
                **record_kwargs,
            )
            f_s = ex.submit(
                record,
                out_dir=seg_s_dir,
                duration=args.stage_seconds,
                director_seconds=0,
                stage_seconds=args.stage_seconds,
                **record_kwargs,
            )
            f_d.result()
            f_s.result()
        print(f"[done] director mp4: {seg_d_dir / 'demo.mp4'}")
        print(f"[done] stage    mp4: {seg_s_dir / 'demo.mp4'}")
    else:
        webm_path = record(
            out_dir=out_dir,
            duration=total_duration,
            director_seconds=args.director_seconds,
            stage_seconds=args.stage_seconds,
            **record_kwargs,
        )
        print(f"[done] webm: {webm_path}")
        print(f"[done] mp4:  {out_dir / 'demo.mp4'}")
        print(f"[done] log:  {out_dir / 'recording.log'}")

    # ponytail: 录制完自动暂停 run，避免空转烧 LLM token。
    try:
        status_after = run_status(args.api_base, created.id)
        if status_after.get("status") == "running":
            _request_json("POST", f"{args.api_base}/runs/{created.id}/pause", timeout=30)
            print(f"[done] run {created.id} 已暂停（停止 scheduler）")
        else:
            print(f"[done] run 当前 status={status_after.get('status')}，无需暂停")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 暂停 run 失败：{exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
