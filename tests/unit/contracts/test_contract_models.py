"""Contract tests for the shared domain models and the fingerprint."""

from __future__ import annotations

import copy
import dataclasses

import pytest

from neon_armada.contracts import versions
from neon_armada.contracts.fingerprint import canonical_state_bytes, state_fingerprint
from neon_armada.contracts.models import (
    BUILD_COST,
    INITIAL_BASE_ENERGY,
    MAX_MAP_SIZE,
    MAX_TICKS_LIMIT,
    MIN_MAP_SIZE,
    SHIP_CAPACITY,
    Action,
    ContractError,
    Exclusion,
    MatchConfig,
    MatchResult,
    MatchState,
    Ship,
    StaticMap,
)


def test_official_constants() -> None:
    assert (MIN_MAP_SIZE, MAX_MAP_SIZE) == (32, 64)
    assert INITIAL_BASE_ENERGY == 1000
    assert SHIP_CAPACITY == 100
    assert BUILD_COST == 500
    assert MAX_TICKS_LIMIT == 500


def test_all_contract_versions_are_one() -> None:
    assert versions.MODELS_VERSION == 1
    assert versions.PROTOCOL_VERSION == 1
    assert versions.HISTORY_VERSION == 1
    assert versions.CLI_VERSION == 1
    assert versions.GENERATOR_VERSION == 1


def test_action_deltas_use_top_left_origin() -> None:
    assert Action.NORTH.delta == (0, -1)
    assert Action.SOUTH.delta == (0, 1)
    assert Action.EAST.delta == (1, 0)
    assert Action.WEST.delta == (-1, 0)
    assert Action.STAY.delta == (0, 0)


def test_config_defaults_and_round_trip() -> None:
    config = MatchConfig()
    assert config.map_size == 32
    assert config.max_ticks == 500
    assert MatchConfig.from_dict(config.to_dict()) == config


@pytest.mark.parametrize(
    "field,value",
    [
        ("map_size", 31),
        ("map_size", 65),
        ("max_ticks", 0),
        ("max_ticks", 501),
        ("move_budget", -1),
        ("tick_timeout_ms", 0),
        ("memory_limit_mb", 1),
        ("map_size", True),
        ("map_size", "32"),
        ("map_size", 32.0),
    ],
)
def test_config_rejects_out_of_range_values(field: str, value: object) -> None:
    data = MatchConfig().to_dict()
    data[field] = value
    with pytest.raises(ContractError):
        MatchConfig.from_dict(data)


def test_config_rejects_missing_field() -> None:
    data = MatchConfig().to_dict()
    del data["move_budget"]
    with pytest.raises(ContractError, match="move_budget"):
        MatchConfig.from_dict(data)


def test_models_are_immutable() -> None:
    ship = Ship(id=0, owner=0, x=1, y=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ship.x = 2  # type: ignore[misc]


def test_static_map_fixture_round_trip(load_fixture) -> None:
    data = load_fixture("contracts/init.valid.json")["map"]
    static_map = StaticMap.from_dict(data)
    assert static_map.to_dict() == data
    assert static_map.kind_at(3, 4) == "0"
    assert static_map.kind_at(28, 27) == "1"
    assert static_map.kind_at(5, 5) == "#"
    assert static_map.in_bounds(31, 31)
    assert not static_map.in_bounds(32, 0)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.update(size=31),
        lambda m: m["cells"].pop(),
        lambda m: m["cells"].__setitem__(0, "." * 31),
        lambda m: m["cells"].__setitem__(0, "?" + "." * 31),
        lambda m: m["cells"].__setitem__(0, "0" + "." * 31),
        lambda m: m.update(bases=[[0, 0], [28, 27]]),
        lambda m: m.update(bases=[[3, 4]]),
        lambda m: m.pop("cells"),
    ],
)
def test_static_map_rejects_invalid_documents(load_fixture, mutate) -> None:
    data = load_fixture("contracts/init.valid.json")["map"]
    mutate(data)
    with pytest.raises(ContractError):
        StaticMap.from_dict(data)


def test_state_fixture_round_trip_and_pinned_fingerprint(load_fixture) -> None:
    fixture = load_fixture("contracts/state.valid.json")
    state = MatchState.from_dict(fixture["state"])
    assert state.to_dict() == fixture["state"]
    # Pinned value: the canonical encoding must never change inside version 1.
    assert state_fingerprint(state) == fixture["fingerprint"]
    assert len(fixture["fingerprint"]) == 64


def test_canonical_bytes_are_sorted_compact_ascii(load_fixture) -> None:
    state = MatchState.from_dict(load_fixture("contracts/state.valid.json")["state"])
    encoded = canonical_state_bytes(state)
    assert b" " not in encoded and b"\n" not in encoded
    assert encoded.startswith(b'{"energy":[[10,2,350],[21,29,350]],"invalid_commands"')


def test_fingerprint_changes_with_state(load_fixture) -> None:
    data = load_fixture("contracts/state.valid.json")["state"]
    base = state_fingerprint(MatchState.from_dict(data))
    changed = copy.deepcopy(data)
    changed["ships"][0]["cargo"] = 1
    assert state_fingerprint(MatchState.from_dict(changed)) != base


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s["ships"].reverse(),
        lambda s: s["ships"].append(dict(s["ships"][0])),
        lambda s: s.update(next_ship_id=1),
        lambda s: s["energy"].reverse(),
        lambda s: s["energy"][0].__setitem__(2, 0),
        lambda s: s.update(reserves=[1000]),
        lambda s: s.update(reserves=[-1, 0]),
        lambda s: s.update(pending_builds=[0, 1]),
        lambda s: s["ships"][0].update(cargo=101),
        lambda s: s["ships"][0].update(owner=2),
        lambda s: s.pop("tick"),
    ],
)
def test_state_rejects_invalid_documents(load_fixture, mutate) -> None:
    data = load_fixture("contracts/state.valid.json")["state"]
    mutate(data)
    with pytest.raises(ContractError):
        MatchState.from_dict(data)


def test_result_round_trip_and_validation(load_fixture) -> None:
    data = load_fixture("contracts/history.valid.json")["result"]
    result = MatchResult.from_dict(data)
    assert result.to_dict() == data

    with_exclusion = dataclasses.replace(
        result, exclusions=(None, Exclusion(tick=17, reason="timeout"))
    )
    assert MatchResult.from_dict(with_exclusion.to_dict()) == with_exclusion

    for key, value in (
        ("end_reason", "bored"),
        ("decided_by", "coin"),
        ("winner", 2),
        ("winner", None),  # null winner requires decided_by == "draw"
    ):
        broken = dict(data)
        broken[key] = value
        with pytest.raises(ContractError):
            MatchResult.from_dict(broken)


def test_exclusion_rejects_unknown_reason() -> None:
    with pytest.raises(ContractError):
        Exclusion(tick=1, reason="bribed")
