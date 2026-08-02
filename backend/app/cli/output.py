from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.padding import Padding
from rich.table import Table
from rich.text import Text


class Renderer:
    def __init__(self, mode: str = "table", *, console: Console | None = None) -> None:
        self.mode = mode
        self.console = console or Console()

    def data(self, value: Any) -> None:
        if self.mode == "json":
            self.console.print_json(json.dumps(value, ensure_ascii=False, default=str))
        elif self.mode == "ndjson":
            values = value if isinstance(value, list) else [value]
            for item in values:
                self._ndjson_line(item)
        elif isinstance(value, Mapping):
            self.key_values(value)
        else:
            self.console.print(value)

    def key_values(self, value: Mapping[str, Any], *, title: str | None = None) -> None:
        if self.mode != "table":
            self.data(dict(value))
            return
        table = Table(title=title, show_header=False, box=None)
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value")
        for key, item in value.items():
            table.add_row(str(key), self._cell(item))
        self.console.print(table)

    def rows(
        self,
        rows: Sequence[Mapping[str, Any]],
        columns: Sequence[tuple[str, str]],
        *,
        title: str | None = None,
    ) -> None:
        if self.mode != "table":
            self.data(list(rows))
            return
        table = Table(title=title)
        for key, label in columns:
            table.add_column(label, no_wrap=key in {"id", "tick", "status"})
        for row in rows:
            table.add_row(*(self._cell(row.get(key)) for key, _ in columns))
        self.console.print(table)

    def event(self, value: Mapping[str, Any]) -> None:
        if self.mode in {"json", "ndjson"}:
            self.data(dict(value))
            return
        payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else {}
        event_type = str(value.get("event_type") or "event")
        actor = value.get("actor_name") or payload.get("actor_name") or "world"
        target = value.get("target_name") or payload.get("target_name")
        location = value.get("location_name") or payload.get("location_name")
        world_time = value.get("world_time") or payload.get("world_time")
        context = " · ".join(
            str(item)
            for item in (world_time, f"tick {value.get('tick_no', '?')}", location)
            if item
        )
        self.console.print(f"[dim]{escape(context)}[/dim]")

        if event_type == "speech":
            message = payload.get("message") or "说了些什么"
            speaker = f"{actor} → {target}" if target else str(actor)
            self.console.print(Text(speaker, style="bold cyan"), soft_wrap=True)
            self.console.print(Padding(Text(f"“{message}”"), (0, 0, 0, 2)))
        elif event_type == "listen":
            speaker = target or payload.get("speaker_name") or "对方"
            self.console.print(
                f"[bold cyan]{escape(str(actor))}[/bold cyan] 正在听 {escape(str(speaker))}"
            )
        elif event_type == "move":
            origin = payload.get("from_location_name") or payload.get("from_location_id") or "?"
            destination = (
                payload.get("to_location_name") or payload.get("to_location_id") or location or "?"
            )
            arrival = payload.get("arrival_tick")
            arrival_text = f" · 预计 tick {arrival} 到达" if arrival is not None else ""
            self.console.print(
                f"[bold cyan]{escape(str(actor))}[/bold cyan]：{escape(str(origin))} → "
                f"{escape(str(destination))}[dim]{escape(arrival_text)}[/dim]"
            )
        elif event_type.startswith("director_"):
            message = payload.get("message") or event_type.removeprefix("director_")
            self.console.print(f"[bold magenta]导演[/bold magenta]：{escape(str(message))}")
        elif event_type == "conversation_started":
            participants = f" 与 {escape(str(target))}" if target else ""
            self.console.print(
                f"[bold cyan]{escape(str(actor))}[/bold cyan]{participants} 开始交谈"
            )
        else:
            suffix = f" → {escape(str(target))}" if target else ""
            self.console.print(
                f"[bold cyan]{escape(str(actor))}[/bold cyan]{suffix} "
                f"[bold]{escape(event_type)}[/bold]"
            )
        self.console.print()

    def _ndjson_line(self, value: Any) -> None:
        """Write exactly one physical line without Rich terminal wrapping."""
        self.console.file.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
        self.console.file.flush()

    @staticmethod
    def _cell(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)


def compact(value: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    return {key: value.get(key) for key in keys}
