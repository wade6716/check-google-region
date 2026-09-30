import os
import tempfile
import unittest
from check_google_region.storage import RegionState, StackState, StateManager


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.temp_dir.name, "test_state.json")
        self.manager = StateManager(self.state_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_dual_stack_json(self):
        state = RegionState(
            ipv4=StackState(country="US", ip="1.2.3.4", updated_at="2026-09-30T10:00:00Z"),
            ipv6=StackState(country="HK", ip="2400::1", updated_at="2026-09-30T10:00:00Z"),
            hostname="test-host",
        )
        saved = self.manager.save(state)
        self.assertTrue(saved)
        self.assertTrue(os.path.exists(self.state_file))

        loaded = self.manager.load()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.ipv4.country, "US")
        self.assertEqual(loaded.ipv4.ip, "1.2.3.4")
        self.assertEqual(loaded.ipv6.country, "HK")
        self.assertEqual(loaded.ipv6.ip, "2400::1")
        self.assertEqual(loaded.country, "US")  # compatibility property
        self.assertEqual(loaded.hostname, "test-host")

    def test_load_legacy_single_stack_json(self):
        # Simulate old version json format
        old_json_content = '{"country": "JP", "ip": "5.6.7.8", "updated_at": "2026-09-30", "hostname": "old-host"}'
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write(old_json_content)

        loaded = self.manager.load()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.ipv4.country, "JP")
        self.assertEqual(loaded.ipv4.ip, "5.6.7.8")
        self.assertIsNone(loaded.ipv6.country)

    def test_load_legacy_txt_migration(self):
        legacy_txt = os.path.join(self.temp_dir.name, "test_state.txt")
        with open(legacy_txt, "w", encoding="utf-8") as f:
            f.write("SG\n")

        # When json doesn't exist, it should fallback to .txt
        loaded = self.manager.load()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.country, "SG")
        self.assertEqual(loaded.ipv4.country, "SG")
        self.assertIsNone(loaded.ipv6.country)


if __name__ == "__main__":
    unittest.main()
