"""FastAPI backend for the web UI.

Credentials and settings are stored in a ``.env`` file edited through the UI.
The OAuth token lives next to it in ``.token.json``. All heavy lifting reuses
the same client/rules/tasks code as the CLI.
"""

from __future__ import annotations

import os
import threading
import uuid
from collections import Counter
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
except ImportError as exc:  # pragma: no cover
    raise ImportError(str(exc))

from .auth import NeedAuthError
from .config import config_from_env
from .core import ConfigError, make_client, make_oauth
from .rules import build_plan, parse_rules
from .tasks import collect_stats, export_rates, list_counts

# Mapping between UI/.env keys and the SHIKI_* environment variables.
ENV_KEYS = {
    "client_id": "SHIKI_CLIENT_ID",
    "client_secret": "SHIKI_CLIENT_SECRET",
    "user": "SHIKI_USER",
    "user_agent": "SHIKI_USER_AGENT",
    "redirect_uri": "SHIKI_REDIRECT_URI",
    "base_url": "SHIKI_BASE_URL",
    "request_delay": "SHIKI_REQUEST_DELAY",
}

# Set by run_server(); the directory of .env also holds .token.json.
_ENV_FILE = ".env"


# --------------------------------------------------------------------------- #
# .env helpers
# --------------------------------------------------------------------------- #
def _read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _write_env_file(values: dict[str, str]) -> None:
    lines = ["# Managed by shikimori-manager web UI. Do not commit.\n"]
    for key, val in values.items():
        lines.append(f'{key}={val}\n')
    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _apply_env() -> None:
    """Load the .env into the process environment (override stale values)."""
    load_dotenv(_ENV_FILE, override=True)


def _token_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(_ENV_FILE)) or ".", ".token.json")


def _current_config():
    _apply_env()
    return config_from_env(token_file=_token_path())


def _client_or_400():
    cfg = _current_config()
    try:
        return make_client(cfg), cfg
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NeedAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class ConfigIn(BaseModel):
    client_id: str = ""
    client_secret: Optional[str] = None  # None = keep existing
    user: str = ""
    user_agent: str = "shikimori-manager"
    redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob"
    base_url: str = "https://shikimori.one"
    request_delay: float = 0.3


class CodeIn(BaseModel):
    code: str


class RunIn(BaseModel):
    rules: list[dict[str, Any]]
    apply: bool = False
    sample: int = 50


# --------------------------------------------------------------------------- #
# Background job runner (for the rule mover, which can take a while)
# --------------------------------------------------------------------------- #
# In-memory store: job_id -> progress/result dict. Fine for a single-process,
# single-user local tool.
_JOBS: dict[str, dict] = {}


def _run_job(job_id: str, cfg, rules, apply: bool, sample: int) -> None:
    job = _JOBS[job_id]
    try:
        client = make_client(cfg)
        user_id = client.resolve_user(cfg.user)

        def on_progress(stage: str, current: int, total: int) -> None:
            job["phase"] = stage          # "fetching" | "scanning"
            job["current"] = current
            job["total"] = total

        plan = build_plan(client, user_id, rules,
                          log=lambda *_: None, on_progress=on_progress)

        summary = Counter((m.rule.media, m.rule.source, m.rule.target) for m in plan)
        moves = [{
            "title": m.title,
            "media": m.rule.media,
            "source": m.rule.source,
            "target": m.rule.target,
            "progress": m.progress,
            "rating": m.rating,
        } for m in plan]

        applied = 0
        errors: list[str] = []
        if apply:
            job["phase"] = "applying"
            job["current"] = 0
            job["total"] = len(plan)
            for m in plan:
                try:
                    client.update_status(m.rate["id"], m.rule.target)
                    applied += 1
                except Exception as exc:  # noqa: BLE001 - report, keep going
                    errors.append(f"{m.title}: {exc}")
                job["current"] = applied + len(errors)

        job["result"] = {
            "total": len(plan),
            "applied": applied,
            "summary": [
                {"media": md, "source": s, "target": t, "count": n}
                for (md, s, t), n in sorted(summary.items())
            ],
            "moves": moves[:sample],
            "truncated": len(moves) > sample,
            "errors": errors,
        }
        job["phase"] = "done"
        job["state"] = "done"
    except (ConfigError, NeedAuthError) as exc:
        job["state"] = "error"
        job["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        job["state"] = "error"
        job["error"] = str(exc)


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
def create_app() -> "FastAPI":
    app = FastAPI(title="shikimori-manager", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # local tool; the server binds to localhost by default
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"ok": True}

    # ---- configuration ------------------------------------------------- #
    @app.get("/api/config")
    def get_config():
        env = _read_env_file()
        return {
            "client_id": env.get("SHIKI_CLIENT_ID", ""),
            "user": env.get("SHIKI_USER", ""),
            "user_agent": env.get("SHIKI_USER_AGENT", "shikimori-manager"),
            "redirect_uri": env.get("SHIKI_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob"),
            "base_url": env.get("SHIKI_BASE_URL", "https://shikimori.one"),
            "request_delay": float(env.get("SHIKI_REQUEST_DELAY", "0.3")),
            "has_secret": bool(env.get("SHIKI_CLIENT_SECRET")),
        }

    @app.post("/api/config")
    def save_config(body: ConfigIn):
        env = _read_env_file()
        payload = body.model_dump()
        # Keep the existing secret when the field is left blank/None.
        secret = payload.pop("client_secret")
        for key, env_key in ENV_KEYS.items():
            if key in payload:
                env[env_key] = str(payload[key])
        if secret:
            env["SHIKI_CLIENT_SECRET"] = secret
        _write_env_file(env)
        _apply_env()
        return {"ok": True}

    # ---- auth ---------------------------------------------------------- #
    @app.get("/api/auth/url")
    def auth_url():
        cfg = _current_config()
        try:
            oauth = make_oauth(cfg)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"url": oauth.authorize_url()}

    @app.get("/api/auth/status")
    def auth_status():
        cfg = _current_config()
        try:
            make_oauth(cfg).valid_token()
        except (ConfigError, NeedAuthError):
            return {"authorized": False}
        return {"authorized": True}

    @app.post("/api/auth/code")
    def auth_code(body: CodeIn):
        cfg = _current_config()
        try:
            make_oauth(cfg).exchange_code(body.code.strip())
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except NeedAuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    # ---- data ---------------------------------------------------------- #
    @app.get("/api/me")
    def me():
        client, cfg = _client_or_400()
        who = client.whoami() or {}
        return {"id": who.get("id"), "nickname": who.get("nickname")}

    @app.get("/api/lists")
    def lists(media: str = "anime"):
        client, cfg = _client_or_400()
        user_id = client.resolve_user(cfg.user)
        return {"user_id": user_id, "media": media,
                "counts": list_counts(client, user_id, media)}

    @app.get("/api/stats")
    def stats(media: str = "anime"):
        client, cfg = _client_or_400()
        user_id = client.resolve_user(cfg.user)
        return {"user_id": user_id, "media": media,
                "stats": collect_stats(client, user_id, media)}

    @app.get("/api/export")
    def export(status: Optional[str] = None, media: str = "anime"):
        client, cfg = _client_or_400()
        user_id = client.resolve_user(cfg.user)
        statuses = [status] if status else None
        data = export_rates(client, user_id, statuses, media)
        return JSONResponse(data)

    # ---- the rule mover (runs as a background job with progress) ------- #
    @app.post("/api/run")
    def run(body: RunIn):
        # Validate eagerly so the user gets immediate feedback.
        try:
            rules = parse_rules(body.rules)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not rules:
            raise HTTPException(status_code=400, detail="No rules provided.")
        cfg = _current_config()

        job_id = uuid.uuid4().hex
        _JOBS[job_id] = {
            "state": "running", "phase": "starting",
            "current": 0, "total": 0, "result": None, "error": None,
        }
        threading.Thread(
            target=_run_job,
            args=(job_id, cfg, rules, body.apply, body.sample),
            daemon=True,
        ).start()
        return {"job_id": job_id}

    @app.get("/api/run/{job_id}")
    def run_status(job_id: str):
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Unknown job id.")
        return job

    # ---- static frontend (if built) ------------------------------------ #
    dist = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
    dist = os.path.abspath(dist)
    if os.path.isdir(dist):
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")

    return app


def run_server(host: str = "127.0.0.1", port: int = 8000, env_file: str = ".env") -> None:
    global _ENV_FILE
    _ENV_FILE = env_file
    _apply_env()
    app = create_app()
    print(f"shikimori-manager UI on http://{host}:{port}")
    print("(If the frontend isn't built yet, run the Vite dev server in web/ "
          "and use http://localhost:5173)")
    uvicorn.run(app, host=host, port=port)
