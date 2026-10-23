import json
import sys
from pathlib import Path

from app import create_app


def main(target: Path) -> None:
    schema = create_app().openapi()
    target.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"OpenAPI: {len(schema['paths'])} путей → {target}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
