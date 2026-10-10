"""Import every module without network access and validate global registration."""

import socket
from pathlib import Path
from unittest.mock import patch

from core.module_manager import ModuleManager
from scripts.ci.contract import discover_modules


def _deny_network(*args, **kwargs):
    raise RuntimeError("network access is forbidden during application smoke")


def main() -> int:
    expected = discover_modules(Path.cwd())
    manager = ModuleManager()
    with patch.object(socket.socket, "connect", _deny_network):
        loaded = manager.discover_and_load()

    errors = manager.get_errors()
    loaded_ids = sorted(module.id for module in manager.get_all_modules())
    if errors:
        for error in errors:
            print(f"{error['module']}: {error['error']}")
        return 1
    if loaded != len(expected):
        print(f"expected {len(expected)} modules, loaded {loaded}: {loaded_ids}")
        return 1

    print(f"Application smoke: {loaded} modules loaded ({', '.join(loaded_ids)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
