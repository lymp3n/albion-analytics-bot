import unittest

from utils.command_permissions_catalog import get_role_assist_catalog
from utils.shotcaller_role_ids import SHOTCALLER_ROLE_IDS


class TestRoleAssistCatalog(unittest.TestCase):
    def test_catalog_shape(self):
        data = get_role_assist_catalog()
        self.assertIn("sections", data)
        self.assertIsInstance(data["sections"], list)
        self.assertGreater(len(data["sections"]), 0)
        ids = [s["id"] for s in data["sections"]]
        self.assertEqual(len(ids), len(set(ids)), "section ids must be unique")
        for sec in data["sections"]:
            self.assertIn("title", sec)
            self.assertIn("rows", sec)
            for row in sec["rows"]:
                self.assertIn("command", row)
                self.assertIn("description", row)

    def test_shotcaller_ids_in_response(self):
        data = get_role_assist_catalog()
        self.assertEqual(set(data.get("shotcaller_role_ids", [])), set(SHOTCALLER_ROLE_IDS))


if __name__ == "__main__":
    unittest.main()
