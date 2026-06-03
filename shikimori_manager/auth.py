"""OAuth2 token handling for Shikimori.

The flow is:
  1. ``authorize_url()`` -> user opens it, approves, copies the one-time code.
  2. ``exchange_code(code)`` -> swaps the code for access + refresh tokens,
     persisted to a JSON file.
  3. ``valid_token()`` -> returns a fresh access token, transparently
     refreshing via the refresh token when it is about to expire.
"""

from __future__ import annotations

import json
import os
import time
from urllib.parse import urlencode

import requests


class NeedAuthError(RuntimeError):
    """Raised when there is no usable token and no way to refresh it."""


class TokenStore:
    """Reads/writes the token JSON ({access_token, refresh_token, expires_at})."""

    def __init__(self, path: str) -> None:
        self.path = path

    def load(self) -> dict | None:
        if not os.path.exists(self.path):
            return None
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, payload: dict) -> dict:
        data = {
            "access_token": payload["access_token"],
            "refresh_token": payload.get("refresh_token", ""),
            "expires_at": payload.get("created_at", int(time.time()))
            + payload.get("expires_in", 0),
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data


class OAuth:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        user_agent: str,
        redirect_uri: str,
        base_url: str,
        store: TokenStore,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.redirect_uri = redirect_uri
        self.base_url = base_url.rstrip("/")
        self.store = store

    # ------------------------------------------------------------------ #
    def authorize_url(self, scope: str = "user_rates") -> str:
        query = urlencode({
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope,
        })
        return f"{self.base_url}/oauth/authorize?{query}"

    def _post(self, payload: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}/oauth/token",
            headers={"User-Agent": self.user_agent},
            data=payload,
            timeout=30,
        )
        if resp.status_code >= 400:
            raise NeedAuthError(f"OAuth error {resp.status_code}: {resp.text}")
        return resp.json()

    def exchange_code(self, code: str) -> str:
        """Swap a one-time authorization code for tokens; returns access token."""
        saved = self.store.save(self._post({
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }))
        return saved["access_token"]

    def _refresh(self, refresh_token: str) -> dict:
        return self.store.save(self._post({
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }))

    def valid_token(self) -> str:
        """Return a fresh access token, refreshing if needed.

        Raises NeedAuthError if there is no stored token / refresh token.
        """
        creds = self.store.load()
        if not creds:
            raise NeedAuthError("No stored token. Run the 'auth' command first.")
        # Refresh a minute early to avoid races with expiry.
        if creds.get("expires_at", 0) - 60 <= time.time():
            if not creds.get("refresh_token"):
                raise NeedAuthError("Token expired and no refresh token. Re-run 'auth'.")
            creds = self._refresh(creds["refresh_token"])
        return creds["access_token"]
