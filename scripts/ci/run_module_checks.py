"""Run the isolated contract and tests for one FazTestBot module."""

from __future__ import annotations

import argparse
import importlib
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from core.module_base import BaseModule
from scripts.ci.contract import discover_modules, read_legacy_allowlist


def _deny_network(*args, **kwargs):
    raise RuntimeError("network access is forbidden during module import")


def validate_module(root: Path, module_name: str) -> BaseModule:
    available = discover_modules(root)
    if module_name not in available:
        raise RuntimeError(f"unknown module: {module_name}")

    with patch.object(socket.socket, "connect", _deny_network):
        package = importlib.import_module(f"modules.{module_name}")

    export_name = f"{module_name}_module"
    if not hasattr(package, export_name):
        raise RuntimeError(f"modules.{module_name} must export {export_name}")
    instance = getattr(package, export_name)
    if not isinstance(instance, BaseModule):
        raise RuntimeError(f"{export_name} must inherit BaseModule")
    valid, message = instance.validate()
    if not valid:
        raise RuntimeError(f"{module_name} failed validation: {message}")
    if len(instance.callback_prefix.encode("utf-8")) >= 64:
        raise RuntimeError(f"{module_name} callback prefix leaves no room for actions")
    return instance


def run_tests(root: Path, module_name: str) -> bool:
    test_dir = root / "tests" / module_name
    if not test_dir.is_dir():
        if module_name not in read_legacy_allowlist(root):
            raise RuntimeError(f"tests/{module_name} is required")
        print(f"{module_name}: legacy import/contract smoke passed; tests are grandfathered")
        return True

    suite = unittest.defaultTestLoader.discover(
        str(test_dir), pattern="test_*.py", top_level_dir=str(root / "tests")
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


def run_quality(root: Path, module_name: str) -> None:
    """Apply the strict quality gate once a module leaves the legacy allowlist."""
    if module_name in read_legacy_allowlist(root):
        print(f"{module_name}: legacy module quality gate is deferred")
        return

    targets = [f"modules/{module_name}", f"tests/{module_name}"]
    subprocess.run([sys.executable, "-m", "ruff", "check", *targets], cwd=root, check=True)
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", *targets],
        cwd=root,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    args = parser.parse_args()
    root = Path.cwd()

    instance = validate_module(root, args.module)
    print(
        f"{args.module}: {instance.name} v{instance.version}, "
        f"callback prefix {instance.callback_prefix!r}"
    )
    run_quality(root, args.module)
    return 0 if run_tests(root, args.module) else 1


if __name__ == "__main__":
    raise SystemExit(main())
