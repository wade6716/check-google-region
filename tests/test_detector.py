import re
import unittest
from unittest.mock import MagicMock, patch
from check_google_region.detector import DetectionResult, RegionDetector


class TestDetector(unittest.TestCase):
    def test_parse_youtube_country_code(self):
        sample_html = '<html><script>var data = {"countryCode":"HK","other":123};</script></html>'
        match = re.search(r'"(countryCode|GL)":"([A-Z]{2})"', sample_html)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(2), "HK")

    def test_parse_youtube_gl_code(self):
        sample_html = '<html><script>var data = {"GL":"JP"};</script></html>'
        match = re.search(r'"(countryCode|GL)":"([A-Z]{2})"', sample_html)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(2), "JP")

    @patch.object(RegionDetector, "get_google_region")
    @patch.object(RegionDetector, "get_public_ip")
    def test_detect_structure(self, mock_ip, mock_region):
        mock_region.return_value = ("US", "YouTube Premium")
        mock_ip.return_value = "198.51.100.1"

        detector = RegionDetector()
        res = detector.detect(fetch_ip=True)

        self.assertIsInstance(res, DetectionResult)
        self.assertEqual(res.country, "US")
        self.assertEqual(res.public_ip, "198.51.100.1")
        self.assertEqual(res.source, "YouTube Premium")


if __name__ == "__main__":
    unittest.main()
