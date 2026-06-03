"""Configuration loading: TOML file + environment overrides + defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for 3.10 and older
    import tomli as tomllib  # type: ignore

from .rules import Rule, parse_rules

DEFAULT_USER_AGENT = "shikimori-manager"
DEFAULT_BASE_URL = "https://shikimori.one"
DEFAULT_REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
DEFAULT_TOKEN_FILE = ".token.json"


@dataclass
class Config:
    client_id: str
    client_secret: str
    redirect_uri: str
    user: str
    user_agent: str
    request_delay: float
    base_url: str
    token_file: str
    rules: list[Rule] = field(default_factory=list)


def load_config(path: str) -> Config:
    """Load config from ``path`` (TOML). Secrets may be overridden by env vars:
    SHIKI_CLIENT_ID, SHIKI_CLIENT_SECRET, SHIKI_USER, SHIKI_USER_AGENT.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file '{path}' not found. "
            f"Copy config.example.toml to config.toml and fill it in."
        )
    with open(path, "rb") as f:
        data = tomllib.load(f)

    auth = data.get("auth", {})
    settings = data.get("settings", {})

    token_file = settings.get("token_file", DEFAULT_TOKEN_FILE)
    # Resolve a relative token path against the config file's directory so the
    # tool behaves the same regardless of the current working directory.
    if not os.path.isabs(token_file):
        token_file = os.path.join(os.path.dirname(os.path.abspath(path)), token_file)

    return Config(
        client_id=os.environ.get("SHIKI_CLIENT_ID", auth.get("client_id", "")),
        client_secret=os.environ.get("SHIKI_CLIENT_SECRET", auth.get("client_secret", "")),
        redirect_uri=auth.get("redirect_uri", DEFAULT_REDIRECT_URI),
        user=os.environ.get("SHIKI_USER", str(settings.get("user", ""))),
        user_agent=os.environ.get("SHIKI_USER_AGENT", settings.get("user_agent", DEFAULT_USER_AGENT)),
        request_delay=float(settings.get("request_delay", 0.3)),
        base_url=settings.get("base_url", DEFAULT_BASE_URL),
        token_file=token_file,
        rules=parse_rules(data.get("rules", [])),
    )


def config_from_env(token_file: str | None = None) -> Config:
    """Build a Config purely from environment variables and defaults.

    Used by the web UI, which manages credentials via a .env file rather than a
    TOML config. Rules are supplied per-request, so they default to empty here.
    """
    tf = token_file or os.environ.get("SHIKI_TOKEN_FILE", DEFAULT_TOKEN_FILE)
    if not os.path.isabs(tf):
        tf = os.path.abspath(tf)
    return Config(
        client_id=os.environ.get("SHIKI_CLIENT_ID", ""),
        client_secret=os.environ.get("SHIKI_CLIENT_SECRET", ""),
        redirect_uri=os.environ.get("SHIKI_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        user=os.environ.get("SHIKI_USER", ""),
        user_agent=os.environ.get("SHIKI_USER_AGENT", DEFAULT_USER_AGENT),
        request_delay=float(os.environ.get("SHIKI_REQUEST_DELAY", "0.3")),
        base_url=os.environ.get("SHIKI_BASE_URL", DEFAULT_BASE_URL),
        token_file=tf,
        rules=[],
    )
