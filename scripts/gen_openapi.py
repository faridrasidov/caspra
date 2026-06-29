# scripts/gen_openapi.py

"""Export the OpenAPI schema for SDK generation in separate repos."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app

OUTPUT = ROOT / "openapi.json"


def main() -> int:
    schema = app.openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote OpenAPI schema to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
