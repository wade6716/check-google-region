import unittest
from check_google_region.cli import parse_args


class TestCli(unittest.TestCase):
    def test_parse_flags(self):
        args = parse_args(["--check"])
        self.assertTrue(args.check)
        self.assertFalse(args.test_email)

        args = parse_args(["--daemon", "--interval", "300"])
        self.assertTrue(args.daemon)
        self.assertEqual(args.interval, 300)

        args = parse_args(["--proxy", "http://127.0.0.1:1080"])
        self.assertEqual(args.proxy, "http://127.0.0.1:1080")


if __name__ == "__main__":
    unittest.main()
