"""
Export the OpenAPI schema to a JSON file.

Usage (from the backend/ directory):
    python export_openapi.py
    python export_openapi.py --output ../docs/openapi.json
"""

import argparse
import json
from pathlib import Path

from main import create_app


def export_openapi(output_path: Path) -> None:
    app = create_app()
    schema = app.openapi()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2))
    print(f"OpenAPI schema written to {output_path.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export OpenAPI schema to JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./openapi.json"),
        help="Destination file path (default: ./openapi.json)",
    )
    args = parser.parse_args()
    export_openapi(args.output)
