"""The position rule (D-076, T22): the generated module against the golden vectors."""

from __future__ import annotations

import json
import re
from types import ModuleType

import pytest

from vehicle_codegen import config, gen_position


def _load(rule: dict) -> ModuleType:
    module = ModuleType("position_under_test")
    exec(compile(gen_position.generate_python(rule), "position.py", "exec"), module.__dict__)
    return module


@pytest.fixture(scope="module")
def position() -> ModuleType:
    return _load(gen_position.load_rule())


@pytest.fixture(scope="module")
def vectors() -> dict:
    return gen_position.load_vectors()


def test_rule_and_vectors_are_well_formed() -> None:
    assert gen_position.check_rule(gen_position.load_rule()) == []
    assert gen_position.check_vectors(gen_position.load_vectors()) == []


def test_is_position_key_vectors(position, vectors) -> None:
    for case in vectors["is_position_key"]:
        assert position.is_position_key(case["name"]) is case["expected"], case["name"]


def test_drop_position_columns_vectors(position, vectors) -> None:
    for case in vectors["drop_position_columns"]:
        assert position.drop_position_columns(case["columns"]) == case["expected"]


def test_redact_vectors_and_input_is_not_mutated(position, vectors) -> None:
    for case in vectors["redact"]:
        before = json.dumps(case["input"], sort_keys=True)
        assert position.redact(case["input"]) == case["expected"]
        assert json.dumps(case["input"], sort_keys=True) == before


def test_aliases_are_the_same_function(position) -> None:
    assert position.is_position_name is position.is_position_key
    assert position.is_position_path is position.is_position_key


def test_a_weakened_rule_fails_the_vectors(vectors) -> None:
    rule = gen_position.load_rule()
    rule["vertical_tokens"] = [t for t in rule["vertical_tokens"] if t != "height"]
    module = _load(rule)
    wrong = [
        c["name"]
        for c in vectors["is_position_key"]
        if module.is_position_key(c["name"]) != c["expected"]
    ]
    assert wrong, "the vectors must catch a rule without `height`"


def test_rule_check_rejects_bad_rules() -> None:
    rule = gen_position.load_rule()
    rule["vertical_tokens"] = [*rule["vertical_tokens"], "lat"]
    assert gen_position.check_rule(rule)
    rule = gen_position.load_rule()
    rule["horizontal_tokens"] = []
    assert gen_position.check_rule(rule)


def test_vectors_file_has_no_real_coordinates() -> None:
    text = config.POSITION_VECTORS_JSON.read_text(encoding="utf-8")
    assert not re.search(r"\d{1,3}\.\d{4,}", text), "use obviously fake coordinates (D-033)"
