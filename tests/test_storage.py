import os
import tempfile
import unittest
from check_google_region.storage import RegionState, StateManager


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.temp_dir.name, "test_state.json")
        self.manager = StateManager(self.state_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_json(self):
        state = RegionState(
            country="US",
            ip="1.2.3.4",
            updated_at="2026-09-30T10:00:00Z",
            hostname="test-host",
        )
        saved = self.manager.save(state)
        self.assertTrue(saved)
        self.assertTrue(os.path.exists(self.state_file))

        loaded = self.manager.load()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.country, "US")
        self.assertEqual(loaded.ip, "1.2.3.4")
        self.assertEqual(loaded.hostname, "test-host")

    def test_load_legacy_txt_migration(self):
        legacy_txt = os.path.join(self.temp_dir.name, "test_state.txt")
        with open(legacy_txt, "w", encoding="utf-8") as f:
            f.write("SG\n")

        # When json doesn't exist, it should fallback to .txt
        loaded = self.manager.load()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.country, "SG")
        self.assertIsNone(loaded.ip)


if __name__ == "__main__":
    unittest.main()
