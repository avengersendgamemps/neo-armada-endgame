"""Tests for the Qt-free presentation adapter (L08)."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

import neon_armada.client as client_package
from neon_armada.client.presentation import MatchPresentation
from neon_armada.contracts.history import HistoryError
from neon_armada.contracts.replay import parse_history


@pytest.fixture
def document(load_fixture) -> dict:
    return load_fixture("contracts/history.valid.json")


@pytest.fixture
def presentation(document) -> MatchPresentation:
    return MatchPresentation(parse_history(document))


def test_presentation_exposes_match_metadata(presentation) -> None:
    assert presentation.last_tick == 2
    assert presentation.title == "alpha vs beta - seed 7"
    assert [presentation.clamp(t) for t in (-5, 0, 1, 2, 99)] == [0, 0, 1, 2, 2]


def test_initial_frame_shows_map_bases_deposits_and_ships(presentation) -> None:
    frame = presentation.frame(0)
    assert frame.tick == 0 and frame.last_tick == 2
    assert frame.size == 32 and len(frame.cells) == 32
    assert frame.bases == ((3, 4), (28, 27))
    assert frame.cells[5][5] == "#"  # obstacle
    assert frame.energy == ((10, 2, 350), (21, 29, 350))
    assert frame.max_energy == 350
    assert [(s.id, s.owner, s.x, s.y, s.cargo) for s in frame.ships] == [
        (0, 0, 3, 4, 0),
        (1, 1, 28, 27, 0),
    ]
    assert [p.name for p in frame.players] == ["alpha", "beta"]
    assert [p.reserve for p in frame.players] == [1000, 1000]
    assert [p.ships for p in frame.players] == [1, 1]
    assert frame.result_text is None
    assert frame.collisions == ()


def test_frames_follow_the_recorded_events(presentation) -> None:
    first = presentation.frame(1)
    assert [(s.x, s.y) for s in first.ships] == [(4, 4), (27, 27)]
    assert [p.move_budget for p in first.players] == [999, 999]

    last = presentation.frame(2)
    assert last.players[0].reserve == 500
    assert last.players[0].pending_build is True
    assert last.players[1].invalid_commands == 1
    assert last.event_summary == (
        "beta invalid command: obstacle",
        "alpha ordered a ship (500)",
    )
    assert last.result_text == "Winner: beta - decided by score (tick limit)"


def test_frame_rejects_ticks_outside_the_match(presentation) -> None:
    for tick in (-1, 3):
        with pytest.raises(IndexError):
            presentation.frame(tick)


def test_mining_collisions_and_exclusions_are_presented(document) -> None:
    doc = copy.deepcopy(document)
    # Put ship 0 on a deposit so the recorded "mined" event is applicable.
    doc["initial_state"]["ships"][0].update(x=10, y=2)
    doc["ticks"][0]["events"] = [
        {"type": "mined", "ship": 0, "amount": 35},
        {"type": "timeout", "player": 1, "consecutive": 3},
        {"type": "agent_excluded", "player": 1, "reason": "timeout"},
    ]
    doc["ticks"][1]["events"] = [
        {"type": "collision", "x": 10, "y": 2, "ships": [0, 1], "energy_added": 35}
    ]
    doc["result"]["exclusions"] = [None, {"tick": 1, "reason": "timeout"}]
    presentation = MatchPresentation(parse_history(doc))

    assert presentation.frame(0).players[1].excluded is None
    first = presentation.frame(1)
    assert first.ships[0].mining is True and first.ships[0].cargo == 35
    assert first.ships[1].mining is False
    assert (10, 2, 315) in first.energy
    assert first.players[1].excluded == "timeout at tick 1"
    assert "beta excluded: timeout" in first.event_summary

    second = presentation.frame(2)
    assert second.ships == ()
    assert second.collisions == ((10, 2),)
    assert (10, 2, 350) in second.energy
    assert [p.ships for p in second.players] == [0, 0]


def test_draw_result_text(document) -> None:
    document["result"].update(winner=None, decided_by="draw")
    presentation = MatchPresentation(parse_history(document))
    assert presentation.frame(2).result_text == "Draw (tick limit)"


def test_from_file_loads_and_rejects_bad_files(document, tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    good.write_text(json.dumps(document), encoding="utf-8")
    assert MatchPresentation.from_file(good).last_tick == 2

    bad = tmp_path / "bad.json"
    bad.write_text("{ nope", encoding="utf-8")
    with pytest.raises(HistoryError):
        MatchPresentation.from_file(bad)
    with pytest.raises(HistoryError):
        MatchPresentation.from_file(tmp_path / "missing.json")

    document["ticks"][0]["events"][0]["ship"] = 77  # cannot be reconstructed
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(HistoryError):
        MatchPresentation.from_file(broken)


def test_client_never_imports_engine_internals() -> None:
    """Architecture rule: the GUI may only use the shared contracts."""
    root = Path(client_package.__file__).parent
    checked = 0
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith("neon_armada.engine"), (path, name)
        checked += 1
    assert checked >= 5


def test_presentation_module_does_not_depend_on_qt() -> None:
    source = (Path(client_package.__file__).parent / "presentation.py").read_text(
        encoding="utf-8"
    )
    assert "PySide6" not in source
