"""Tests for SAP query parameter resolution."""

import pytest
from infrastructure.sap.param_resolver import (
    extract_param_indices,
    has_parameters,
    resolve_parameters,
)


class TestHasParameters:
    def test_no_params(self):
        assert not has_parameters("SELECT * FROM T0 WHERE x = 'foo'")

    def test_single_param(self):
        assert has_parameters("WHERE x = '[%0]'")

    def test_multiple_params(self):
        assert has_parameters("WHERE x = '[%0]' AND y = '[%1]'")

    def test_repeated_param(self):
        assert has_parameters("WHERE x = '[%0]' OR y = '[%0]'")


class TestExtractParamIndices:
    def test_no_params(self):
        assert extract_param_indices("SELECT 1") == []

    def test_single_param(self):
        assert extract_param_indices("WHERE x = '[%0]'") == [0]

    def test_multiple_params(self):
        assert extract_param_indices("WHERE x = '[%0]' AND y = '[%1]'") == [0, 1]

    def test_repeated_dedup(self):
        assert extract_param_indices("WHERE x = '[%0]' AND y = '[%0]' AND z = '[%2]'") == [0, 2]

    def test_out_of_order(self):
        assert extract_param_indices("WHERE x = '[%2]' AND y = '[%0]'") == [0, 2]


class TestResolveParameters:
    def test_single_replacement(self):
        sql = "WHERE x = '[%0]'"
        resolved, used = resolve_parameters(sql, {0: "TEST123"})
        assert resolved == "WHERE x = 'TEST123'"
        assert used == {0: "TEST123"}

    def test_multiple_replacements(self):
        sql = "WHERE x = '[%0]' AND y = '[%1]'"
        resolved, used = resolve_parameters(sql, {0: "A", 1: "B"})
        assert resolved == "WHERE x = 'A' AND y = 'B'"
        assert used == {0: "A", 1: "B"}

    def test_repeated_param(self):
        sql = "WHERE x = '[%0]' OR y = '[%0]'"
        resolved, used = resolve_parameters(sql, {0: "SERIAL123"})
        assert resolved == "WHERE x = 'SERIAL123' OR y = 'SERIAL123'"
        assert used == {0: "SERIAL123"}

    def test_default_for_missing(self):
        sql = "WHERE x = '[%0]' AND y = '[%1]'"
        resolved, used = resolve_parameters(sql, {0: "A"}, default="DEFAULT")
        assert resolved == "WHERE x = 'A' AND y = 'DEFAULT'"
        assert used == {0: "A", 1: "DEFAULT"}

    def test_no_params_passthrough(self):
        sql = "SELECT * FROM T0"
        resolved, used = resolve_parameters(sql, {})
        assert resolved == sql
        assert used == {}

    def test_real_query_serial(self):
        sql = "WHERE T0.manufSN = '[%0]' AND T0.callType = 2"
        resolved, used = resolve_parameters(sql, {0: "ABC-12345"})
        assert resolved == "WHERE T0.manufSN = 'ABC-12345' AND T0.callType = 2"
        assert used == {0: "ABC-12345"}
