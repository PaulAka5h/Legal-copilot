"""Write the backend OpenAPI schema for frontend type generation: uv run python scripts/export_openapi.py"""

import json
from pathlib import Path

from app.main import create_app

target = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
target.write_text(json.dumps(create_app().openapi(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {target}")
