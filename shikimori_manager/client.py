"""Thin HTTP client for the Shikimori API.

Handles the mandatory ``User-Agent`` header, bearer auth, polite rate limiting
and the quirks of the ``/api/v2/user_rates`` endpoint (which ignores
``limit``/``page`` and returns the whole list on every page).
"""

from __future__ import annotations

import time
from typing import Callable, Iterable

import requests


class ShikimoriError(RuntimeError):
    """Raised for non-recoverable API errors (4xx/5xx, exhausted retries)."""


class ShikimoriClient:
    def __init__(
        self,
        token: str,
        user_agent: str,
        *,
        base_url: str = "https://shikimori.one",
        request_delay: float = 0.3,
        max_retries: int = 5,
        timeout: int = 30,
    ) -> None:
        self.token = token
        self.user_agent = user_agent
        self.base_url = base_url.rstrip("/")
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, *, params=None, json=None):
        headers = {
            "User-Agent": self.user_agent,
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        url = self.base_url + path
        for attempt in range(self.max_retries):
            resp = self._session.request(
                method, url, headers=headers, params=params, json=json,
                timeout=self.timeout,
            )
            # Stay under Shikimori's 5 rps / 90 rpm limits.
            time.sleep(self.request_delay)
            if resp.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                raise ShikimoriError(
                    f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}"
                )
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise ShikimoriError(f"{method} {path}: rate limit not cleared after retries")

    # ------------------------------------------------------------------ #
    def whoami(self) -> dict | None:
        """Return the user owning the current token (or None)."""
        return self._request("GET", "/api/users/whoami")

    def resolve_user(self, user: str | int | None) -> int:
        """Resolve a numeric id, a nickname, or the token's owner to a user id."""
        if user in (None, ""):
            me = self.whoami()
            if not me:
                raise ShikimoriError("Cannot determine current user from token.")
            return me["id"]
        if str(user).isdigit():
            return int(user)
        found = self._request("GET", "/api/users", params={"search": user, "limit": 1})
        if not found:
            raise ShikimoriError(f"User '{user}' not found.")
        return found[0]["id"]

    def fetch_rates(
        self, user_id: int, status: str, *, target_type: str = "Anime",
    ) -> list[dict]:
        """Fetch every user_rate for ``status`` and ``target_type`` (Anime/Manga).

        The endpoint may ignore ``limit``/``page`` and return the full list on
        each page, so we stop as soon as a page brings no new ids instead of
        relying on the page size (which would loop forever).
        """
        rates: list[dict] = []
        seen: set[int] = set()
        page = 1
        while True:
            batch = self._request("GET", "/api/v2/user_rates", params={
                "user_id": user_id,
                "target_type": target_type,
                "status": status,
                "limit": 1000,
                "page": page,
            }) or []
            fresh = [r for r in batch if r["id"] not in seen]
            if not fresh:
                break
            seen.update(r["id"] for r in fresh)
            rates.extend(fresh)
            page += 1
        return rates

    def fetch_meta(
        self,
        ids: Iterable[int],
        *,
        media: str = "anime",
        progress: Callable[[int, int], None] | None = None,
    ) -> dict[int, dict]:
        """Return ``{id: {"score": float, "name": str|None}}`` for anime or manga.

        Fetched in batches of 50. The manga list mixes in light novels, which
        ``/api/mangas`` silently omits, so any ids it doesn't return are looked
        up via ``/api/ranobe`` as a fallback.
        """
        endpoints = ["/api/mangas", "/api/ranobe"] if media == "manga" else ["/api/animes"]
        ids = list(dict.fromkeys(ids))  # de-dupe, keep order
        meta: dict[int, dict] = {}
        remaining = ids
        for ep_index, endpoint in enumerate(endpoints):
            if not remaining:
                break
            still_missing: list[int] = []
            for i in range(0, len(remaining), 50):
                chunk = remaining[i:i + 50]
                data = self._request("GET", endpoint, params={
                    "ids": ",".join(str(x) for x in chunk),
                    "limit": 50,
                }) or []
                returned = {item["id"] for item in data}
                for item in data:
                    try:
                        score = float(item.get("score"))
                    except (TypeError, ValueError):
                        score = 0.0
                    meta[item["id"]] = {"score": score, "name": item.get("name")}
                still_missing.extend(x for x in chunk if x not in returned)
                # Report progress on the primary endpoint pass only.
                if progress and ep_index == 0:
                    progress(min(i + 50, len(ids)), len(ids))
            remaining = still_missing
        return meta

    def update_status(self, rate_id: int, status: str) -> None:
        """Move a user_rate to another list."""
        self._request("PATCH", f"/api/v2/user_rates/{rate_id}",
                      json={"user_rate": {"status": status}})
