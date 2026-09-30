import os
import tempfile
import unittest
from check_google_region.config import Config, load_dotenv


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = Config.from_env()
        self.assertIsNotNone(cfg.state_file)
        self.assertEqual(cfg.smtp_port, int(os.getenv("SMTP_PORT", "465")))
        self.assertFalse(cfg.insecure_ssl)
        self.assertEqual(cfg.interval, 3600)
        self.assertFalse(cfg.daemon_mode)

    def test_interval_env(self):
        os.environ["CHECK_INTERVAL"] = "1800"
        try:
            cfg = Config.from_env()
            self.assertEqual(cfg.interval, 1800)
        finally:
            os.environ.pop("CHECK_INTERVAL", None)

    def test_load_dotenv(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
            f.write("# comment line\n")
            f.write("TEST_KEY_CUSTOM_ENV=custom_value_123\n")
            f.write("TEST_QUOTED_VAL=\"quoted\"\n")
            temp_path = f.name

        try:
            load_dotenv(temp_path)
            self.assertEqual(os.getenv("TEST_KEY_CUSTOM_ENV"), "custom_value_123")
            self.assertEqual(os.getenv("TEST_QUOTED_VAL"), "quoted")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            os.environ.pop("TEST_KEY_CUSTOM_ENV", None)
            os.environ.pop("TEST_QUOTED_VAL", None)


if __name__ == "__main__":
    unittest.main()
