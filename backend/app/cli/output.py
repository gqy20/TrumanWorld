from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from rich.console import Console
from rich.table import Table


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
                self.console.print(json.dumps(item, ensure_ascii=False, default=str), markup=False)
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
            self.console.print(json.dumps(value, ensure_ascii=False, default=str), markup=False)
            return
        actor = value.get("actor_name") or value.get("actor_agent_id") or "world"
        target = value.get("target_name") or value.get("target_agent_id")
        suffix = f" → {target}" if target else ""
        self.console.print(
            f"[dim]tick {value.get('tick_no', '?')}[/dim] "
            f"[cyan]{actor}[/cyan]{suffix} [bold]{value.get('event_type', 'event')}[/bold]"
        )

    @staticmethod
    def _cell(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)


def compact(value: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    return {key: value.get(key) for key in keys}
