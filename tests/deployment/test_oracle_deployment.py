from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "deploy" / "oracle"


def _working_bash_is_available() -> bool:
    if not shutil.which("bash"):
        return False
    result = subprocess.run(
        ["bash", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "bash" in result.stdout.lower()


class OracleDeploymentContractTests(unittest.TestCase):
    def test_service_uses_single_unprivileged_process_and_persistent_storage(self):
        unit = (ORACLE / "faztestbot.service").read_text(encoding="utf-8")

        self.assertIn("User=faztestbot", unit)
        self.assertIn(
            "ExecStartPre=/opt/faztestbot/current/.venv/bin/python -m scripts.doctor",
            unit,
        )
        self.assertIn("ExecStart=/opt/faztestbot/current/.venv/bin/python bot.py", unit)
        self.assertIn("ReadWritePaths=/var/lib/faztestbot", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertNotIn("EnvironmentFile=", unit)

    def test_environment_template_contains_no_populated_token(self):
        environment = (ORACLE / "faztestbot.env.example").read_text(encoding="utf-8")

        self.assertIn("BOT_TOKEN=\n", environment)
        self.assertIn("FAZTESTBOT_DATA_DIR=/var/lib/faztestbot", environment)
        self.assertNotRegex(environment, r"\d{8,12}:[A-Za-z0-9_-]{30,}")

    def test_release_deployer_enforces_verification_and_health_boundaries(self):
        deployer = (ORACLE / "deploy-release.sh").read_text(encoding="utf-8")

        for required in (
            "flock --nonblock",
            "sha256sum --check --strict",
            "-m scripts.release verify --tag",
            "-m scripts.doctor --json",
            "-m scripts.database backup",
            "-m scripts.liveness --json",
            "candidate failed liveness; attempting code rollback",
        ):
            with self.subTest(required=required):
                self.assertIn(required, deployer)

    @unittest.skipUnless(_working_bash_is_available(), "bash is unavailable on this host")
    def test_shell_assets_parse_as_bash(self):
        for script in ("bootstrap.sh", "deploy-release.sh"):
            with self.subTest(script=script):
                subprocess.run(
                    ["bash", "-n"],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                    input=(ORACLE / script).read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
