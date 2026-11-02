"""Create a local .env file with fresh random secrets (refuses to overwrite an existing one).

Usage, from the repository root:  python infra/scripts/make_env.py
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".env.example"
TARGET = ROOT / ".env"

GENERATED = {
    "POSTGRES_PASSWORD": lambda: secrets.token_hex(24),
    "NEWTON_APP_DB_PASSWORD": lambda: secrets.token_hex(24),
    "JWT_SECRET": lambda: secrets.token_hex(48),
}


def main() -> None:
    if TARGET.exists():
        sys.exit(".env already exists: nothing changed.")
    lines = []
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0]
        if not line.startswith("#") and key in GENERATED:
            line = f"{key}={GENERATED[key]()}"
        lines.append(line)
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(".env created with random secrets.")


if __name__ == "__main__":
    main()
