"""CLI entry point for configured-provider product embedding generation."""

from __future__ import annotations

import argparse
import json

from fashion_search.embeddings.pipeline import run_embedding_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate configured-provider embeddings for the fashion catalog.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect products without calling the provider or writing embeddings.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of products to inspect in this run.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override EMBEDDING_BATCH_SIZE for this run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    stats = run_embedding_pipeline(
        dry_run=args.dry_run,
        limit=args.limit,
        batch_size=args.batch_size,
    )
    print(json.dumps(stats.as_dict(), indent=2))


if __name__ == "__main__":
    main()
