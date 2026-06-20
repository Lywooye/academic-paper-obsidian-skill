from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from scripts import config as pipeline_config  # noqa: E402
from scripts import queue_convert_and_notify  # noqa: E402


class QueueConvertAndNotifyTests(unittest.TestCase):
    def make_config(self, tmp_path: Path) -> dict:
        return pipeline_config.deep_merge(
            pipeline_config.DEFAULT_CONFIG,
            {
                "vaultRoot": str(tmp_path / "vault"),
                "mineru": {"python": "/usr/bin/python3"},
                "openclaw": {
                    "cli": "/usr/local/bin/openclaw",
                    "commandCwd": str(tmp_path / "repo"),
                    "channel": "feishu",
                    "notifyToEnv": "TEST_OPENCLAW_NOTIFY_TO",
                    "outputMaxBytes": 9000,
                    "timeoutGraceSec": 120,
                },
            },
        )

    def test_build_cron_command_uses_config_without_private_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf = tmp_path / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            cfg = self.make_config(tmp_path)
            args = queue_convert_and_notify.parse_args(
                [
                    str(pdf),
                    "--config",
                    "config.json",
                    "--zotero-id",
                    "ABCDEFGH",
                    "--timeout-sec",
                    "3600",
                ]
            )
            command = queue_convert_and_notify.build_cron_command(args, cfg)
            self.assertEqual(command[0], "/usr/local/bin/openclaw")
            self.assertIn("--announce", command)
            self.assertIn("--command-argv", command)
            self.assertIn("--timeout-seconds", command)
            self.assertIn("3720", command)
            self.assertNotIn("user:", command)

    def test_delivery_target_can_come_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.make_config(Path(tmp))
            old_value = queue_convert_and_notify.os.environ.get("TEST_OPENCLAW_NOTIFY_TO")
            queue_convert_and_notify.os.environ["TEST_OPENCLAW_NOTIFY_TO"] = "user:test"
            try:
                self.assertEqual(queue_convert_and_notify.optional_delivery_target(cfg), "user:test")
            finally:
                if old_value is None:
                    queue_convert_and_notify.os.environ.pop("TEST_OPENCLAW_NOTIFY_TO", None)
                else:
                    queue_convert_and_notify.os.environ["TEST_OPENCLAW_NOTIFY_TO"] = old_value


if __name__ == "__main__":
    unittest.main()

