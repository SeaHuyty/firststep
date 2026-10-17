"""Write the API's OpenAPI schema for the frontend's type generator.

python scripts/export_openapi.py ../client/openapi.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.app import create_app


def main() -> None:
    """Dump the schema to the path given (default: stdout)."""
    schema = create_app().openapi()
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
