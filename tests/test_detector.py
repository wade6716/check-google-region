import unittest
from unittest.mock import MagicMock, patch
from check_google_region.detector import DetectionResult, RegionDetector, StackResult


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.detector = RegionDetector()

    def test_parse_youtube_cn_lockout(self):
        # 即使页面带有全局兜底 "GL":"US"，只要包含 www.google.cn，必须准确判定为 CN
        sample_html = (
            '<html>'
            '<script>ytcfg.set({"GL":"US","HL":"zh-CN"});</script>'
            '<div>Premium is not available in your country</div>'
            '<a href="https://www.google.cn/intl/zh-CN/policies/terms/">服务条款</a>'
            '</html>'
        )
        country, source = self.detector.parse_youtube_premium_html(sample_html)
        self.assertEqual(country, "CN")
        self.assertIn("CN Lockout", source)

    def test_parse_youtube_unavailable_with_gl_us(self):
        # 页面提示不可用，且只有 "GL":"US"，不能误报为 US
        sample_html = (
            '<html>'
            '<script>ytcfg.set({"GL":"US"});</script>'
            '<div>Premium is not available in your country</div>'
            '</html>'
        )
        country, source = self.detector.parse_youtube_premium_html(sample_html)
        self.assertIsNone(country)

    def test_parse_youtube_normal_unlocked_countrycode(self):
        # 正常可用国家，且含有 countryCode
        sample_html = (
            '<html>'
            '<div>Ad-free videos, downloads, and background play</div>'
            '<script>var config = {"countryCode":"HK","GL":"HK"};</script>'
            '</html>'
        )
        country, source = self.detector.parse_youtube_premium_html(sample_html)
        self.assertEqual(country, "HK")
        self.assertEqual(source, "YouTube Premium")

    def test_parse_youtube_normal_innertube_gl(self):
        # 正常可用国家，且含有 INNERTUBE_CONTEXT_GL
        sample_html = (
            '<html>'
            '<div>1-month free trial, ad-free music</div>'
            '<script>ytcfg.set({"INNERTUBE_CONTEXT_GL":"JP","GL":"JP"});</script>'
            '</html>'
        )
        country, source = self.detector.parse_youtube_premium_html(sample_html)
        self.assertEqual(country, "JP")
        self.assertEqual(source, "YouTube Premium")

    def test_parse_youtube_normal_gl(self):
        # 正常可用国家，只包含 GL 和 ad-free 标识
        sample_html = (
            '<html>'
            '<div>Ad-free and background play</div>'
            '<script>ytcfg.set({"GL":"US"});</script>'
            '</html>'
        )
        country, source = self.detector.parse_youtube_premium_html(sample_html)
        self.assertEqual(country, "US")

    @patch.object(RegionDetector, "get_google_region")
    @patch.object(RegionDetector, "get_public_ip")
    def test_detect_structure(self, mock_ip, mock_region):
        mock_region.return_value = ("US", "YouTube Premium")
        mock_ip.return_value = "198.51.100.1"

        res = self.detector.detect(fetch_ip=True)
        self.assertIsInstance(res, StackResult)
        self.assertEqual(res.country, "US")
        self.assertEqual(res.public_ip, "198.51.100.1")
        self.assertEqual(res.source, "YouTube Premium")


if __name__ == "__main__":
    unittest.main()
