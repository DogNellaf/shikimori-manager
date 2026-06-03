"""Unit tests for rule parsing, matching and the planning engine.

These are pure-logic tests: the Shikimori client is replaced by a fake, so no
network access or credentials are needed.
"""

import pytest

from shikimori_manager.rules import Rule, build_plan, parse_rules


# --------------------------------------------------------------------------- #
# Rule.matches
# --------------------------------------------------------------------------- #
def test_progress_bounds():
    r = Rule(name="x", media="anime", source="planned", target="watching", min_progress=1)
    assert r.matches(progress=3, score=0, rating=0.0)
    assert not r.matches(progress=0, score=0, rating=0.0)


def test_rating_bounds_and_needs_rating():
    r = Rule(name="x", media="anime", source="planned", target="on_hold", min_rating=8.01)
    assert r.needs_rating()
    assert r.matches(progress=0, score=0, rating=8.5)
    assert not r.matches(progress=0, score=0, rating=8.0)


def test_personal_score_bounds():
    r = Rule(name="x", media="manga", source="dropped", target="planned", max_score=0)
    assert r.matches(progress=0, score=0, rating=0.0)
    assert not r.matches(progress=0, score=7, rating=0.0)


# --------------------------------------------------------------------------- #
# parse_rules validation + aliases
# --------------------------------------------------------------------------- #
def test_parse_rejects_bad_status():
    with pytest.raises(ValueError):
        parse_rules([{"source": "nope", "target": "planned"}])


def test_parse_rejects_bad_media():
    with pytest.raises(ValueError):
        parse_rules([{"media": "novel", "source": "planned", "target": "watching"}])


def test_parse_rejects_unknown_key():
    with pytest.raises(ValueError):
        parse_rules([{"source": "planned", "target": "watching", "min_eps": 1}])


def test_aliases_map_to_canonical():
    # chapters -> progress, anime_score -> rating
    [r] = parse_rules([{
        "source": "planned", "target": "on_hold",
        "max_chapters": 0, "min_anime_score": 8.01,
    }])
    assert r.max_progress == 0
    assert r.min_rating == 8.01
    assert r.media == "anime"  # default


def test_conflicting_aliases_error():
    with pytest.raises(ValueError):
        parse_rules([{"source": "planned", "target": "watching",
                      "min_episodes": 1, "min_progress": 2}])


# --------------------------------------------------------------------------- #
# build_plan with a fake client
# --------------------------------------------------------------------------- #
def rate(rate_id, target_id, *, episodes=0, chapters=0, score=0):
    return {"id": rate_id, "target_id": target_id,
            "episodes": episodes, "chapters": chapters, "score": score}


class FakeClient:
    def __init__(self, rates_by_key, scores, names=None):
        # rates_by_key keyed by (target_type, status)
        self._rates = rates_by_key
        self._scores = scores
        self._names = names or {}
        self.meta_calls = []

    def fetch_rates(self, user_id, status, *, target_type="Anime"):
        return self._rates.get((target_type, status), [])

    def fetch_meta(self, ids, *, media="anime", progress=None):
        self.meta_calls.append(media)
        return {i: {"score": self._scores.get(i, 0.0), "name": self._names.get(i)}
                for i in ids}


def test_first_matching_rule_wins_and_ratings_lazy():
    rules = parse_rules([
        {"name": "watch", "source": "planned", "target": "watching", "min_episodes": 1},
        {"name": "hold", "source": "planned", "target": "on_hold",
         "max_episodes": 0, "min_anime_score": 8.01},
    ])
    rates = [
        rate(10, 100, episodes=2),  # -> watching (no rating lookup)
        rate(11, 101, episodes=0),  # rating 9.0 -> on_hold
        rate(12, 102, episodes=0),  # rating 7.0 -> stays
    ]
    client = FakeClient(
        {("Anime", "planned"): rates},
        scores={101: 9.0, 102: 7.0},
        names={100: "Title A", 101: "Title B"},
    )

    plan = build_plan(client, 1, rules, log=lambda *_: None)
    result = {m.rate["id"]: m.rule.target for m in plan}

    assert result == {10: "watching", 11: "on_hold"}
    assert 12 not in result
    started = next(m for m in plan if m.rate["id"] == 10)
    assert started.rating is None
    # Titles resolved: rating-free move (100) and rating move (101).
    assert {m.title for m in plan} == {"Title A", "Title B"}


def test_manga_uses_chapters_and_manga_endpoint():
    rules = parse_rules([
        {"media": "manga", "source": "planned", "target": "watching", "min_chapters": 1},
    ])
    rates = [rate(20, 200, chapters=5), rate(21, 201, chapters=0)]
    client = FakeClient({("Manga", "planned"): rates}, scores={})

    plan = build_plan(client, 1, rules, log=lambda *_: None)
    assert [m.rate["id"] for m in plan] == [20]
    assert plan[0].progress == 5
    assert plan[0].media_key == "manga"
