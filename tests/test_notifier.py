import unittest
from unittest.mock import MagicMock, patch
from check_google_region.config import Config
from check_google_region.notifier import Notifier


class TestNotifier(unittest.TestCase):
    def setUp(self):
        self.config = Config(
            state_file="/tmp/test.json",
            smtp_server="smtp.example.com",
            smtp_port=465,
            smtp_user="test@example.com",
            smtp_pass="password",
            receiver_email="receiver@example.com",
            insecure_ssl=False,
            proxy=None,
            telegram_bot_token=None,
            telegram_chat_id=None,
            webhook_url=None,
        )
        self.notifier = Notifier(self.config)

    @patch.object(Notifier, "_send_email")
    def test_send_alert_email_called(self, mock_send):
        mock_send.return_value = True

        ok = self.notifier.send_alert(
            old_country="US",
            new_country="CN",
            public_ip="1.2.3.4",
            source="YouTube",
        )
        self.assertTrue(ok)
        mock_send.assert_called_once()
        subject, text_content, html_content = mock_send.call_args[0]
        self.assertIn("CN", subject)
        self.assertIn("1.2.3.4", text_content)
        self.assertIn("1.2.3.4", html_content)


if __name__ == "__main__":
    unittest.main()
