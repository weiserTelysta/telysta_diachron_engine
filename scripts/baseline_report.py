"""Run legacy golden scenarios and print a canonical JSON baseline report."""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.engine.golden import GOLDEN_SCENARIOS, run_legacy_golden_scenario


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=888)
    parser.add_argument("--scenario", choices=GOLDEN_SCENARIOS, action="append")
    args = parser.parse_args()

    scenarios = args.scenario or list(GOLDEN_SCENARIOS)
    results = []
    with tempfile.TemporaryDirectory(prefix="telysta-baseline-") as temp_dir:
        root = Path(temp_dir)
        for index, scenario in enumerate(scenarios):
            with redirect_stdout(io.StringIO()):
                results.append(
                    run_legacy_golden_scenario(
                        scenario,
                        args.seed,
                        root / f"{index:02d}-{scenario}",
                    )
                )
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
