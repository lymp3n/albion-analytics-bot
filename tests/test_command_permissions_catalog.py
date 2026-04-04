import unittest

from utils.command_permissions_catalog import get_role_assist_catalog
from utils.shotcaller_role_ids import SHOTCALLER_ROLE_IDS


class TestRoleAssistCatalog(unittest.TestCase):
    def test_catalog_table(self):
        data = get_role_assist_catalog()
        self.assertIn("table", data)
        self.assertIsInstance(data["table"], list)
        self.assertGreaterEqual(len(data["table"]), 4)
        tiers = [r["tier"] for r in data["table"]]
        self.assertIn("Everyone", tiers)
        self.assertIn("Basic", tiers)
        self.assertIn("Staff", tiers)
        self.assertIn("Admin", tiers)
        for row in data["table"]:
            self.assertIn("tier", row)
            self.assertIn("commands", row)
            self.assertIn("details", row)
            self.assertTrue(str(row["commands"]).strip())
            self.assertTrue(str(row["details"]).strip())

    def test_shotcaller_ids_in_response(self):
        data = get_role_assist_catalog()
        self.assertEqual(set(data.get("shotcaller_role_ids", [])), set(SHOTCALLER_ROLE_IDS))


if __name__ == "__main__":
    unittest.main()
