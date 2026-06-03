"""Declarative move rules and the engine that applies them.

A rule moves user_rate entries from one list (``source``) to another
(``target``) for a given ``media`` (anime or manga) when they satisfy optional
numeric conditions. Rules are evaluated top-to-bottom per (media, source); the
first matching rule wins.

Anime and manga share the same structure on Shikimori, so conditions are
media-neutral:
  * progress  = watched episodes (anime) or read chapters (manga)
  * score     = your personal score on the entry
  * rating    = the title's community score on Shikimori
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Optional

# Valid Shikimori list statuses (identical for anime and manga).
VALID_STATUSES = {
    "planned", "watching", "rewatching", "completed", "on_hold", "dropped",
}
VALID_MEDIA = {"anime", "manga"}

# Public condition keys -> canonical field. Aliases let anime users write
# "episodes" and manga users write "chapters" for the same progress condition,
# and keep the older "*_anime_score" keys working.
_ALIASES: dict[str, tuple[str, set[str]]] = {
    # canonical: (bound, {accepted keys})
    "min_progress": ("min", {"min_progress", "min_episodes", "min_chapters"}),
    "max_progress": ("max", {"max_progress", "max_episodes", "max_chapters"}),
    "min_score": ("min", {"min_score"}),
    "max_score": ("max", {"max_score"}),
    "min_rating": ("min", {"min_rating", "min_anime_score", "min_manga_score"}),
    "max_rating": ("max", {"max_rating", "max_anime_score", "max_manga_score"}),
}
_ALL_CONDITION_KEYS = {k for _, keys in _ALIASES.values() for k in keys}


@dataclass
class Rule:
    name: str
    media: str
    source: str
    target: str
    min_progress: Optional[float] = None
    max_progress: Optional[float] = None
    min_score: Optional[float] = None      # personal score on the entry
    max_score: Optional[float] = None
    min_rating: Optional[float] = None     # community score of the title
    max_rating: Optional[float] = None

    def needs_rating(self) -> bool:
        return self.min_rating is not None or self.max_rating is not None

    def matches(self, *, progress: float, score: float, rating: float) -> bool:
        if self.min_progress is not None and progress < self.min_progress:
            return False
        if self.max_progress is not None and progress > self.max_progress:
            return False
        if self.min_score is not None and score < self.min_score:
            return False
        if self.max_score is not None and score > self.max_score:
            return False
        if self.min_rating is not None and rating < self.min_rating:
            return False
        if self.max_rating is not None and rating > self.max_rating:
            return False
        return True


def _resolve_condition(raw: dict, canonical: str, accepted: set[str], where: str):
    """Return the value for a canonical condition, resolving aliases.

    Errors if two different aliases for the same condition disagree.
    """
    present = {k: raw[k] for k in accepted if k in raw}
    if not present:
        return None
    values = set(present.values())
    if len(values) > 1:
        raise ValueError(f"{where}: conflicting values for {canonical}: {present}.")
    return next(iter(values))


def parse_rules(raw_rules: list[dict]) -> list[Rule]:
    """Validate and build Rule objects from parsed config / API input."""
    rules: list[Rule] = []
    for i, raw in enumerate(raw_rules):
        where = f"rule #{i + 1}" + (f" ('{raw['name']}')" if raw.get("name") else "")
        media = raw.get("media", "anime")
        source = raw.get("source")
        target = raw.get("target")
        if media not in VALID_MEDIA:
            raise ValueError(f"{where}: invalid media '{media}'. "
                             f"Expected one of {sorted(VALID_MEDIA)}.")
        if source not in VALID_STATUSES:
            raise ValueError(f"{where}: invalid source '{source}'. "
                             f"Expected one of {sorted(VALID_STATUSES)}.")
        if target not in VALID_STATUSES:
            raise ValueError(f"{where}: invalid target '{target}'. "
                             f"Expected one of {sorted(VALID_STATUSES)}.")
        unknown = set(raw) - _ALL_CONDITION_KEYS - {"name", "media", "source", "target"}
        if unknown:
            raise ValueError(f"{where}: unknown keys {sorted(unknown)}.")

        conditions = {
            canonical: _resolve_condition(raw, canonical, keys, where)
            for canonical, (_, keys) in _ALIASES.items()
        }
        rules.append(Rule(
            name=raw.get("name") or f"{media}: {source} -> {target}",
            media=media,
            source=source,
            target=target,
            **{k: v for k, v in conditions.items() if v is not None},
        ))
    return rules


@dataclass
class Move:
    rate: dict
    rule: Rule
    rating: Optional[float]
    name: Optional[str] = None  # resolved human-readable title

    @property
    def media_key(self) -> str:
        return "manga" if self.rule.media == "manga" else "anime"

    @property
    def progress(self) -> int:
        field = "chapters" if self.rule.media == "manga" else "episodes"
        return self.rate.get(field) or 0

    @property
    def title(self) -> str:
        # Prefer the resolved name, then any embedded object, then a stable id.
        embedded = (self.rate.get(self.media_key) or {}).get("name")
        return self.name or embedded or f"{self.media_key}/{self.rate['target_id']}"


def _progress_of(rate: dict, media: str) -> int:
    field = "chapters" if media == "manga" else "episodes"
    return rate.get(field) or 0


def build_plan(
    client,
    user_id: int,
    rules: list[Rule],
    *,
    log: Callable[[str], None] = print,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> list[Move]:
    """Compute the list of moves without performing them.

    Community ratings are fetched in batches and only for entries that actually
    reach a rating condition. Human-readable titles are then resolved for the
    matched entries (reusing names already fetched during rating lookups).
    ``on_progress(stage, current, total)`` reports progress, where ``stage`` is
    ``"fetching"``, ``"scanning"`` or ``"titling"``.
    """
    def emit(stage: str, current: int = 0, total: int = 0) -> None:
        if on_progress:
            on_progress(stage, current, total)

    # Group by (media, source): each group is one list to fetch.
    by_group: dict[tuple[str, str], list[Rule]] = defaultdict(list)
    for rule in rules:
        by_group[(rule.media, rule.source)].append(rule)

    moves: list[Move] = []
    # Cache of titles keyed by (media, id); seeded from rating lookups for free.
    names: dict[tuple[str, int], str] = {}

    for (media, source), group_rules in by_group.items():
        target_type = "Manga" if media == "manga" else "Anime"
        emit("fetching")
        rates = client.fetch_rates(user_id, source, target_type=target_type)
        log(f"'{media}:{source}': {len(rates)} entries")

        # Pass 1: resolve everything that matches before any rating condition.
        deferred: list[dict] = []
        need_rating_ids: set[int] = set()
        for rate in rates:
            progress = _progress_of(rate, media)
            score = rate.get("score") or 0
            for rule in group_rules:
                if rule.needs_rating():
                    deferred.append(rate)
                    need_rating_ids.add(rate["target_id"])
                    break
                if rule.matches(progress=progress, score=score, rating=0.0):
                    moves.append(Move(rate, rule, None))
                    break

        # Pass 2: fetch ratings for deferred entries and re-evaluate fully.
        if need_rating_ids:
            log(f"  fetching community ratings for {len(need_rating_ids)} {media}...")
            emit("scanning", 0, len(need_rating_ids))

            def report(done, total):
                log(f"  ratings: {done}/{total}")
                emit("scanning", done, total)

            meta = client.fetch_meta(need_rating_ids, media=media, progress=report)
            for item_id, m in meta.items():
                if m.get("name"):
                    names[(media, item_id)] = m["name"]
            for rate in deferred:
                progress = _progress_of(rate, media)
                score = rate.get("score") or 0
                rating = meta.get(rate["target_id"], {}).get("score", 0.0)
                for rule in group_rules:
                    if rule.matches(progress=progress, score=score, rating=rating):
                        moves.append(Move(rate, rule, rating))
                        break

    # Resolve human-readable titles for matched moves not already named
    # (e.g. entries matched by rating-free rules), batched per media.
    _resolve_titles(client, moves, names, emit, log)
    return moves


def _resolve_titles(client, moves, names, emit, log) -> None:
    missing: dict[str, set[int]] = defaultdict(set)
    for m in moves:
        key = (m.rule.media, m.rate["target_id"])
        if key not in names:
            missing[m.rule.media].add(m.rate["target_id"])

    total = sum(len(v) for v in missing.values())
    if total:
        log(f"resolving titles for {total} entries...")
        done = 0
        for media, ids in missing.items():
            meta = client.fetch_meta(ids, media=media)
            for item_id, m in meta.items():
                if m.get("name"):
                    names[(media, item_id)] = m["name"]
            done += len(ids)
            emit("titling", done, total)

    for m in moves:
        m.name = names.get((m.rule.media, m.rate["target_id"]))
