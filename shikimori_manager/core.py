"""Shared construction of OAuth/client objects, used by both CLI and web UI."""

from __future__ import annotations

from .auth import OAuth, TokenStore
from .client import ShikimoriClient
from .config import Config


class ConfigError(RuntimeError):
    """Raised when required configuration (e.g. client credentials) is missing."""


def make_oauth(cfg: Config) -> OAuth:
    if not cfg.client_id or not cfg.client_secret:
        raise ConfigError(
            "Missing client_id/client_secret. Provide them via config/.env "
            "or SHIKI_CLIENT_ID / SHIKI_CLIENT_SECRET."
        )
    return OAuth(
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        user_agent=cfg.user_agent,
        redirect_uri=cfg.redirect_uri,
        base_url=cfg.base_url,
        store=TokenStore(cfg.token_file),
    )


def make_client(cfg: Config) -> ShikimoriClient:
    """Build an authenticated client. May raise ConfigError or NeedAuthError."""
    token = make_oauth(cfg).valid_token()
    return ShikimoriClient(
        token=token,
        user_agent=cfg.user_agent,
        base_url=cfg.base_url,
        request_delay=cfg.request_delay,
    )
