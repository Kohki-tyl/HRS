"""コンテナ／PaaS向けの本番起動エントリーポイント。"""

import os

import uvicorn


def _port() -> int:
    raw_port = os.environ.get("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError("PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be between 1 and 65535")
    return port


def _validate_production_environment() -> None:
    if os.environ.get("HRS_ENV", "").strip().lower() != "production":
        return

    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not password or password == "hrs-admin":
        raise RuntimeError(
            "ADMIN_PASSWORD must be set to a non-default value in production"
        )


def main() -> None:
    _validate_production_environment()
    uvicorn.run(
        "scripts.startup.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=_port(),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "*"),
    )


if __name__ == "__main__":
    main()
