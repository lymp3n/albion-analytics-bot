"""Unit tests for Discord role ID parsing and merge logic (no Discord / DB)."""

import unittest

from utils.role_config import (
    assignment_rows_from_legacy_override,
    effective_sets_from_override_row,
    normalize_ids_for_storage,
    parse_discord_role_ids,
    sets_from_assignment_rows,
    tier_set_from_db_value,
)


class TestParseDiscordRoleIds(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(parse_discord_role_ids(""), [])
        self.assertEqual(parse_discord_role_ids(None), [])

    def test_comma_and_space(self):
        self.assertEqual(
            parse_discord_role_ids("1434197939068342302, 1471208796507603076"),
            [1434197939068342302, 1471208796507603076],
        )

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_discord_role_ids("abc")


class TestNormalizeForStorage(unittest.TestCase):
    def test_blank(self):
        self.assertIsNone(normalize_ids_for_storage(""))
        self.assertIsNone(normalize_ids_for_storage("   \n"))

    def test_sort_unique(self):
        self.assertEqual(
            normalize_ids_for_storage("2, 1, 2"),
            "1, 2",
        )


class TestAssignmentRows(unittest.TestCase):
    def test_legacy_to_rows_priority(self):
        legacy = {
            "member_role_ids": "1, 2",
            "mentor_role_ids": "2, 3",
            "founder_role_ids": "3",
        }
        rows = assignment_rows_from_legacy_override(legacy)
        tiers = {r["discord_role_id"]: r["tier"] for r in rows}
        self.assertEqual(tiers[1], "member")
        self.assertEqual(tiers[2], "mentor")
        self.assertEqual(tiers[3], "founder")

    def test_sets_from_assignments(self):
        m, ment, f = sets_from_assignment_rows(
            [
                {"discord_role_id": 10, "tier": "member"},
                {"discord_role_id": 20, "tier": "mentor"},
            ]
        )
        self.assertEqual(m, {10})
        self.assertEqual(ment, {20})
        self.assertEqual(f, set())


class TestEffectiveSets(unittest.TestCase):
    def test_no_row(self):
        d_m, d_ment, d_f = {1, 2}, {3}, {4}
        m, ment, f = effective_sets_from_override_row(None, d_m, d_ment, d_f)
        self.assertEqual(m, d_m)
        self.assertEqual(ment, d_ment)
        self.assertEqual(f, d_f)

    def test_blank_column_inherits(self):
        d_m, d_ment, d_f = {1}, {2}, {3}
        row = {"member_role_ids": "", "mentor_role_ids": "99", "founder_role_ids": None}
        m, ment, f = effective_sets_from_override_row(row, d_m, d_ment, d_f)
        self.assertEqual(m, d_m)
        self.assertEqual(ment, {99})
        self.assertEqual(f, d_f)

    def test_tier_set_from_db_value(self):
        self.assertEqual(tier_set_from_db_value(None, {1, 2}), {1, 2})
        self.assertEqual(tier_set_from_db_value("10", {1}), {10})


if __name__ == "__main__":
    unittest.main()
