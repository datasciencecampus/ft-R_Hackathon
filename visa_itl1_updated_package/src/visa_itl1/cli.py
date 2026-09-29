from __future__ import annotations
import argparse
from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Allocate Visa spend to ITL1")
    parser.add_argument("--nspl", required=True)
    parser.add_argument("--addressbase", required=True)
    parser.add_argument("--visa", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run_pipeline(
        nspl_path=args.nspl, addressbase_path=args.addressbase,
        visa_path=args.visa, config_path=args.config, output_dir=args.output,
    )

if __name__ == "__main__":
    main()
