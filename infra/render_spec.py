"""Render infra/app-spec.yaml with secrets from .env.do (deployment values) and .env (API keys, JWT secret).

Prints the filled spec to stdout; never write it inside the repository.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip()
    return out


def main() -> None:
    env = {**read_env(ROOT / ".env"), **read_env(ROOT / ".env.do")}
    env.setdefault("APP_URL", "${APP_URL}")  # App Platform bindable variable, resolved by DO
    direct = env.get("DATABASE_URL_DIRECT", "")
    env["DATABASE_URL_MIGRATE"] = direct.replace("postgresql://", "postgresql+psycopg://", 1)
    spec = (ROOT / "infra" / "app-spec.yaml").read_text()
    missing = sorted({k for k in re.findall(r"\$\{([A-Z_]+)\}", spec) if not env.get(k)})
    if missing:
        sys.exit(f"missing values: {', '.join(missing)}")
    sys.stdout.write(re.sub(r"\$\{([A-Z_]+)\}", lambda m: env[m.group(1)], spec))


if __name__ == "__main__":
    main()
