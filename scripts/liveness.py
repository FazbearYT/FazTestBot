"""Report whether the FazTestBot polling process is live and ready."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.process_lock import APPLICATION_LOCK_PATH
from core.runtime_status import RUNTIME_STATUS_PATH, probe_liveness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--status-path", type=Path, default=RUNTIME_STATUS_PATH)
    parser.add_argument("--lock-path", type=Path, default=APPLICATION_LOCK_PATH)
    args = parser.parse_args(argv)

    result = probe_liveness(status_path=args.status_path, lock_path=args.lock_path)
    output = {"live": result.live, "summary": result.summary, "details": result.details}
    if args.as_json:
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(f"Liveness: {'live' if result.live else 'not live'} - {result.summary}")
    return 0 if result.live else 1


if __name__ == "__main__":
    raise SystemExit(main())
