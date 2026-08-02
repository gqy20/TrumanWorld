import io
import json

from rich.console import Console

from app.cli.output import Renderer


def test_ndjson_writes_one_physical_line_per_record():
    stream = io.StringIO()
    renderer = Renderer("ndjson", console=Console(file=stream, width=20, color_system=None))

    renderer.data(
        [
            {"id": "event-1", "message": "a value much wider than the terminal"},
            {"id": "event-2", "message": "第二条很长的事件内容"},
        ]
    )

    lines = stream.getvalue().splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["id"] for line in lines] == ["event-1", "event-2"]


def test_event_renderer_turns_payload_fields_into_a_story():
    stream = io.StringIO()
    renderer = Renderer("table", console=Console(file=stream, color_system=None))

    renderer.event(
        {
            "tick_no": 1,
            "event_type": "speech",
            "world_time": "06:05",
            "payload": {
                "actor_name": "Meryl",
                "target_name": "Truman",
                "location_name": "海滨公寓",
                "message": "广场七点有音乐会。",
            },
        }
    )

    output = stream.getvalue()
    assert "06:05 · tick 1 · 海滨公寓" in output
    assert "Meryl → Truman" in output
    assert "“广场七点有音乐会。”" in output


def test_event_renderer_describes_movement_and_director_events():
    stream = io.StringIO()
    renderer = Renderer("table", console=Console(file=stream, color_system=None))

    renderer.event(
        {
            "tick_no": 2,
            "event_type": "move",
            "payload": {
                "actor_name": "Alice",
                "from_location_name": "咖啡馆",
                "to_location_name": "广场",
                "arrival_tick": 3,
            },
        }
    )
    renderer.event(
        {
            "tick_no": 2,
            "event_type": "director_broadcast",
            "payload": {"message": "音乐会即将开始"},
        }
    )

    output = stream.getvalue()
    assert "Alice：咖啡馆 → 广场 · 预计 tick 3 到达" in output
    assert "导演：音乐会即将开始" in output
