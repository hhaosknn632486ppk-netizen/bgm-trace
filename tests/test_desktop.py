from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from bgm_trace.cli import main
from bgm_trace.desktop import read_observation
from bgm_trace.media import TraceError, digest
from bgm_trace.windows_desktop import WindowsDesktop, _png


def observation(tmp_path):
    image = tmp_path / "window.png"
    image.write_bytes(_png(1, 1, b"\x10\x20\x30\x00"))
    path = tmp_path / "window.json"
    frame = {"schema_version": 1, "kind": "jianying_window_observation",
             "captured_at": datetime.now(timezone.utc).isoformat(), "image": image.name, "image_sha256": digest(image),
             "process_id": 11, "process_started": 22, "window_handle": 33, "active_handle": 33,
             "bounds": [10, 20, 1000, 700], "last_input": 44}
    path.write_text(json.dumps(frame))
    return path, frame


@pytest.mark.parametrize("failure", ["expired", "future", "image_modified", "traversal", "reused", "missing_process"])
def test_unusable_observations_cannot_reach_actions(tmp_path, failure):
    path, frame = observation(tmp_path)
    assert read_observation(path) == frame
    if failure in {"expired", "future"}:
        frame["captured_at"] = (datetime.now(timezone.utc) + timedelta(seconds=-61 if failure == "expired" else 60)).isoformat()
    elif failure == "image_modified":
        (tmp_path / "window.png").write_bytes(b"different")
    elif failure == "traversal":
        frame["image"] = "../window.png"
    elif failure == "reused":
        path.with_suffix(".json.used").write_bytes(b"")
    else:
        del frame["process_id"]
    path.write_text(json.dumps(frame))
    with pytest.raises(TraceError):
        read_observation(path)


@pytest.mark.parametrize("failure", ["process_restart", "other_app", "geometry", "foreground", "input_activity"])
def test_changed_desktop_state_blocks_action(tmp_path, failure):
    _, frame = observation(tmp_path)
    # No Windows APIs or inputs are invoked; exercise the real validation against changed observations.
    desktop = object.__new__(WindowsDesktop)
    desktop.process = lambda pid: {"started": 23 if failure == "process_restart" else 22}
    desktop.owner = lambda handle: 12 if failure == "other_app" else 11
    desktop.bounds = lambda handle: [10, 20, 999, 700] if failure == "geometry" else frame["bounds"]
    desktop.user = SimpleNamespace(GetForegroundWindow=lambda: 99 if failure == "foreground" else 33)
    desktop.last_input = lambda: 45 if failure == "input_activity" else 44
    with pytest.raises(TraceError):
        desktop.validate(frame)


def test_outside_and_covered_clicks_send_no_input(tmp_path):
    _, frame = observation(tmp_path)
    desktop = object.__new__(WindowsDesktop)
    desktop.send = lambda item: pytest.fail("Unsafe click dispatched")
    args = SimpleNamespace(action="click", x=1000, y=30)
    with pytest.raises(TraceError, match="outside"):
        desktop.act(args, frame)
    args.x = 50
    desktop.user = SimpleNamespace(WindowFromPoint=lambda point: 123)
    desktop.owner = lambda handle: 999
    with pytest.raises(TraceError, match="covers"):
        desktop.act(args, frame)


def test_cli_key_requires_an_explicit_key_before_consuming_observation(tmp_path, capsys):
    path, _ = observation(tmp_path)
    assert main(["jianying-desktop", "key", "--frame", str(path)]) == 2
    assert "requires --key" in capsys.readouterr().err
    assert not path.with_suffix(".json.used").exists()


def test_backend_never_dispatches_a_missing_key():
    desktop = object.__new__(WindowsDesktop)
    desktop.key = lambda *args: pytest.fail("A missing key must not send input")
    with pytest.raises(TraceError, match="requires --key"):
        desktop.act(SimpleNamespace(action="key", key=None), {})
