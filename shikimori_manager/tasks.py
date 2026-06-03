"""High-level operations shared by the CLI and the web UI."""

from __future__ import annotations

from .client import ShikimoriClient

# Canonical order in which lists are presented.
STATUS_ORDER = ["planned", "watching", "rewatching", "completed", "on_hold", "dropped"]


def _target_type(media: str) -> str:
    return "Manga" if media == "manga" else "Anime"


def _progress_field(media: str) -> str:
    return "chapters" if media == "manga" else "episodes"


def list_counts(client: ShikimoriClient, user_id: int, media: str = "anime") -> dict[str, int]:
    """Number of entries in each list for the given media."""
    tt = _target_type(media)
    return {s: len(client.fetch_rates(user_id, s, target_type=tt)) for s in STATUS_ORDER}


def collect_stats(client: ShikimoriClient, user_id: int, media: str = "anime") -> dict[str, dict]:
    """Per-list aggregate stats: count, progress (episodes/chapters), rated, avg."""
    tt = _target_type(media)
    field = _progress_field(media)
    stats: dict[str, dict] = {}
    for status in STATUS_ORDER:
        rates = client.fetch_rates(user_id, status, target_type=tt)
        rated = [r.get("score") or 0 for r in rates if (r.get("score") or 0) > 0]
        stats[status] = {
            "count": len(rates),
            "progress": sum(r.get(field) or 0 for r in rates),
            "rated": len(rated),
            "avg_score": round(sum(rated) / len(rated), 2) if rated else 0.0,
        }
    return stats


def export_rates(
    client: ShikimoriClient,
    user_id: int,
    statuses: list[str] | None = None,
    media: str = "anime",
) -> list[dict]:
    """Export user_rate entries (a safe backup) for the given statuses/media."""
    statuses = statuses or STATUS_ORDER
    tt = _target_type(media)
    media_key = "manga" if media == "manga" else "anime"
    out: list[dict] = []
    for status in statuses:
        for r in client.fetch_rates(user_id, status, target_type=tt):
            out.append({
                "id": r["id"],
                "target_id": r["target_id"],
                "media": media_key,
                "status": r.get("status"),
                "score": r.get("score") or 0,
                "episodes": r.get("episodes") or 0,
                "chapters": r.get("chapters") or 0,
                "volumes": r.get("volumes") or 0,
                "rewatches": r.get("rewatches") or 0,
                "name": (r.get(media_key) or {}).get("name"),
            })
    return out
