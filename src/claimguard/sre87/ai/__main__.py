from __future__ import annotations

import argparse
import json
from pathlib import Path

from claimguard.sre87.ai.training import train_risk_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the advisory SRE 87 risk model")
    parser.add_argument("--rows", type=int, default=12_000)
    parser.add_argument("--seed", type=int, default=87)
    parser.add_argument("--no-mlflow", action="store_true")
    parser.add_argument("--model-path", type=Path, default=None)
    args = parser.parse_args()

    kwargs = {
        "rows": args.rows,
        "seed": args.seed,
        "enable_mlflow": not args.no_mlflow,
    }
    if args.model_path is not None:
        kwargs["model_path"] = args.model_path
    result = train_risk_model(**kwargs)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
