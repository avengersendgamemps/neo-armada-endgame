"""Tests for the history reader, reconstruction and comparison (L07)."""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path

import pytest

from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.history import HistoryError
from neon_armada.contracts.models import EnergyCell, MatchState, Ship
from neon_armada.contracts.replay import (
    apply_events,
    compare_histories,
    first_invalid_tick,
    load_history,
    parse_history,
    reconstruct_states,
)


@pytest.fixture
def document(load_fixture) -> dict:
    return load_fixture("contracts/history.valid.json")


def state(**changes) -> MatchState:
    base = MatchState(
        tick=4,
        reserves=(1000, 700),
        move_budgets=(50, 60),
        pending_builds=(False, True),
        invalid_commands=(1, 0),
        next_ship_id=3,
        ships=(Ship(0, 0, 5, 5, 30), Ship(1, 1, 9, 9, 0), Ship(2, 0, 7, 5, 10)),
        energy=(EnergyCell(5, 5, 40), EnergyCell(9, 9, 5)),
    )
    return dataclasses.replace(base, **changes)


# --- reading -------------------------------------------------------------------


def test_fixture_history_is_parsed_into_typed_models(document) -> None:
    history = parse_history(document)
    assert history.seed == 7
    assert history.agent_names == ("alpha", "beta")
    assert history.config.max_ticks == 2
    assert history.static_map.bases == ((3, 4), (28, 27))
    assert [tick.tick for tick in history.ticks] == [1, 2]
    assert history.result.winner == 1


def test_load_history_round_trip_from_disk(document, tmp_path: Path) -> None:
    path = tmp_path / "match.history.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert load_history(path) == parse_history(document)
    assert load_history(str(path)) == parse_history(document)


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"not json at all",
        b'{"format": "neon-armada-history", "history_version": 1, "header": {',
        b"[1, 2, 3]",
        b"\xff\xfe\x00",
        b"{}",
    ],
)
def test_corrupt_or_truncated_files_are_rejected(content, tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_bytes(content)
    with pytest.raises(HistoryError):
        load_history(path)


def test_truncated_real_document_is_rejected(document, tmp_path: Path) -> None:
    text = json.dumps(document)
    path = tmp_path / "cut.json"
    path.write_text(text[: len(text) // 2], encoding="utf-8")
    with pytest.raises(HistoryError, match="not valid JSON"):
        load_history(path)


def test_missing_file_and_directory_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(HistoryError, match="cannot read"):
        load_history(tmp_path / "nope.json")
    with pytest.raises(HistoryError):
        load_history(tmp_path)


@pytest.mark.parametrize("version", [0, 2, 99, "1", None])
def test_unsupported_versions_are_rejected(document, tmp_path, version) -> None:
    document["history_version"] = version
    path = tmp_path / "v.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(HistoryError, match="history_version"):
        load_history(path)


# --- event application ---------------------------------------------------------


def test_events_without_state_effect() -> None:
    events = [
        {"type": "timeout", "player": 0, "consecutive": 1},
        {"type": "agent_excluded", "player": 0, "reason": "timeout"},
    ]
    assert apply_events(state(), events, 5) == state(tick=5)


def test_invalid_command_and_malformed_response_count() -> None:
    events = [
        {"type": "invalid_command", "player": 1, "reason": "obstacle", "ship": 1},
        {"type": "malformed_response", "player": 0},
    ]
    assert apply_events(state(), events, 5).invalid_commands == (2, 1)


def test_build_started_and_ship_spawned() -> None:
    after = apply_events(
        state(),
        [
            {"type": "ship_spawned", "player": 1, "ship": 3, "x": 20, "y": 20},
            {"type": "build_started", "player": 0, "cost": 500},
        ],
        5,
    )
    assert after.reserves == (500, 700)
    assert after.pending_builds == (True, False)
    assert after.ships[-1] == Ship(3, 1, 20, 20, 0)
    assert after.next_ship_id == 4


def test_ship_moved_updates_position_and_owner_budget() -> None:
    after = apply_events(
        state(), [{"type": "ship_moved", "ship": 1, "x": 9, "y": 8}], 5
    )
    assert after.ships[1] == Ship(1, 1, 9, 8, 0)
    assert after.move_budgets == (50, 59)


def test_collision_removes_ships_and_adds_energy() -> None:
    event = {"type": "collision", "x": 6, "y": 5, "ships": [0, 2], "energy_added": 40}
    after = apply_events(state(), [event], 5)
    assert [ship.id for ship in after.ships] == [1]
    assert EnergyCell(6, 5, 40) in after.energy
    empty = dict(event, energy_added=0)
    assert EnergyCell(6, 5, 0) not in apply_events(state(), [empty], 5).energy
    assert len(apply_events(state(), [empty], 5).energy) == 2


def test_mined_moves_energy_from_cell_to_ship_and_removes_empty_cells() -> None:
    after = apply_events(state(), [{"type": "mined", "ship": 0, "amount": 4}], 5)
    assert after.ships[0].cargo == 34
    assert after.energy[0] == EnergyCell(5, 5, 36)
    drained = apply_events(state(), [{"type": "mined", "ship": 1, "amount": 5}], 5)
    assert drained.energy == (EnergyCell(5, 5, 40),)
    assert drained.ships[1].cargo == 5


def test_delivered_moves_cargo_to_reserve() -> None:
    after = apply_events(state(), [{"type": "delivered", "ship": 0, "amount": 30}], 5)
    assert after.reserves == (1030, 700)
    assert after.ships[0].cargo == 0


def test_apply_events_does_not_mutate_the_input_state() -> None:
    before = state()
    snapshot = before.to_dict()
    apply_events(before, [{"type": "ship_moved", "ship": 0, "x": 5, "y": 4}], 5)
    assert before.to_dict() == snapshot


@pytest.mark.parametrize(
    "event",
    [
        {"type": "ship_moved", "ship": 42, "x": 1, "y": 1},
        {"type": "mined", "ship": 42, "amount": 1},
        {"type": "delivered", "ship": 42, "amount": 1},
        {"type": "mined", "ship": 1, "amount": 6},  # more than the cell holds
        {"type": "mined", "ship": 0, "amount": 40},  # cargo above capacity... 70
        {"type": "ship_spawned", "player": 0, "ship": 1, "x": 1, "y": 1},
        {"type": "collision", "x": 1, "y": 1, "ships": [0, 42], "energy_added": 0},
        {"type": "build_started", "player": 1, "cost": 5000},
    ],
)
def test_inconsistent_events_raise_history_error(event) -> None:
    if event == {"type": "mined", "ship": 0, "amount": 40}:
        base = state(ships=(Ship(0, 0, 5, 5, 90),), next_ship_id=1)
    else:
        base = state()
    with pytest.raises(HistoryError):
        apply_events(base, [event], 5)


# --- reconstruction and verification -------------------------------------------


def test_fixture_reconstruction_matches_every_fingerprint(document) -> None:
    history = parse_history(document)
    states = reconstruct_states(history)
    assert len(states) == 3
    assert states[0] == history.initial_state
    assert [s.tick for s in states] == [0, 1, 2]
    for entry, reconstructed in zip(history.ticks, states[1:], strict=True):
        assert state_fingerprint(reconstructed) == entry.fingerprint
    assert first_invalid_tick(history) is None
    # The final reconstructed state agrees with the recorded result.
    assert states[-1].reserves == history.result.scores
    assert states[-1].invalid_commands == history.result.invalid_commands


def test_tampered_event_is_detected_at_its_tick(document) -> None:
    document["ticks"][1]["events"][1]["cost"] = 400
    assert first_invalid_tick(parse_history(document)) == 2


def test_tampered_fingerprint_is_detected_at_its_tick(document) -> None:
    document["ticks"][0]["fingerprint"] = "0" * 64
    assert first_invalid_tick(parse_history(document)) == 1


def test_tampered_initial_state_is_detected_at_tick_zero(document) -> None:
    document["initial_state"]["reserves"] = [999, 1000]
    assert first_invalid_tick(parse_history(document)) == 0


def test_unreconstructable_tick_is_reported(document) -> None:
    document["ticks"][0]["events"][0]["ship"] = 55
    history = parse_history(document)
    assert first_invalid_tick(history) == 1
    with pytest.raises(HistoryError):
        reconstruct_states(history)


# --- comparison ------------------------------------------------------------------


def test_identical_histories_compare_equal_ignoring_agent_names(document) -> None:
    other = copy.deepcopy(document)
    other["header"]["agents"][0]["name"] = "someone else"
    result = compare_histories(parse_history(document), parse_history(other))
    assert result.identical and result.first_divergent_tick is None


@pytest.mark.parametrize(
    "mutate,tick,detail",
    [
        (lambda d: d["header"].update(seed=8), 0, "seed"),
        (lambda d: d["header"]["config"].update(move_budget=5), 0, "config"),
        (lambda d: d["map"]["cells"].__setitem__(0, "#" + "." * 31), 0, "static_map"),
        (lambda d: d.update(initial_fingerprint="a" * 64), 0, "initial_fingerprint"),
        (lambda d: d["ticks"][0].update(fingerprint="b" * 64), 1, "fingerprint"),
        (lambda d: d["ticks"][1].update(fingerprint="c" * 64), 2, "fingerprint"),
    ],
)
def test_first_divergent_tick_is_reported(document, mutate, tick, detail) -> None:
    other = copy.deepcopy(document)
    mutate(other)
    result = compare_histories(parse_history(document), parse_history(other))
    assert not result.identical
    assert result.first_divergent_tick == tick
    assert detail in result.detail
    mirrored = compare_histories(parse_history(other), parse_history(document))
    assert mirrored.first_divergent_tick == tick


def test_shorter_history_diverges_after_its_last_tick(document) -> None:
    shorter = copy.deepcopy(document)
    shorter["ticks"].pop()
    shorter["result"]["ticks_played"] = 1
    result = compare_histories(parse_history(document), parse_history(shorter))
    assert (result.identical, result.first_divergent_tick) == (False, 2)
