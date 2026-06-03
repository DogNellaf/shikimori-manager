"""Command-line interface for shikimori-manager."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from . import __version__
from .auth import NeedAuthError
from .client import ShikimoriError
from .config import Config, load_config
from .core import ConfigError, make_client, make_oauth
from .rules import build_plan
from .tasks import STATUS_ORDER, collect_stats, export_rates, list_counts


def _make_oauth(cfg: Config):
    try:
        return make_oauth(cfg)
    except ConfigError as exc:
        raise SystemExit(str(exc))


def _make_client(cfg: Config):
    try:
        return make_client(cfg)
    except ConfigError as exc:
        raise SystemExit(str(exc))
    except NeedAuthError as exc:
        raise SystemExit(f"{exc}\nRun:  shikimori-manager auth")


# --------------------------------------------------------------------------- #
# Sub-commands
# --------------------------------------------------------------------------- #
def cmd_auth(cfg: Config, args: argparse.Namespace) -> int:
    oauth = _make_oauth(cfg)
    code = args.code
    if not code:
        print("1. Open this URL in your browser and approve access:\n")
        print("   " + oauth.authorize_url())
        print("\n2. Copy the authorization code shown by Shikimori.")
        print("   (The code is single-use and expires in ~2 minutes.)\n")
        try:
            code = input("Paste the code here: ").strip()
        except EOFError:
            print("No code provided.", file=sys.stderr)
            return 1
    if not code:
        print("No code provided.", file=sys.stderr)
        return 1
    try:
        oauth.exchange_code(code)
    except NeedAuthError as exc:
        print(f"Authorization failed: {exc}", file=sys.stderr)
        return 1
    print(f"Token saved to {cfg.token_file}. You're all set.")
    return 0


def cmd_whoami(cfg: Config, args: argparse.Namespace) -> int:
    client = _make_client(cfg)
    me = client.whoami()
    if not me:
        print("Could not identify the current user.", file=sys.stderr)
        return 1
    print(f"id={me['id']}  nickname={me.get('nickname')}")
    return 0


def _media_list(arg: str) -> list[str]:
    return ["anime", "manga"] if arg == "both" else [arg]


def cmd_lists(cfg: Config, args: argparse.Namespace) -> int:
    client = _make_client(cfg)
    user_id = client.resolve_user(cfg.user)
    print(f"User id={user_id}")
    for media in _media_list(args.media):
        print(f"\n[{media}]")
        for status, count in list_counts(client, user_id, media).items():
            print(f"  {status:<11} {count}")
    return 0


def cmd_stats(cfg: Config, args: argparse.Namespace) -> int:
    client = _make_client(cfg)
    user_id = client.resolve_user(cfg.user)
    print(f"User id={user_id}")
    for media in _media_list(args.media):
        unit = "chapters" if media == "manga" else "episodes"
        stats = collect_stats(client, user_id, media)
        print(f"\n[{media}]")
        print(f"  {'list':<11} {'count':>6} {unit:>9} {'rated':>6} {'avg':>5}")
        for status in STATUS_ORDER:
            s = stats[status]
            print(f"  {status:<11} {s['count']:>6} {s['progress']:>9} "
                  f"{s['rated']:>6} {s['avg_score']:>5}")
    return 0


def cmd_export(cfg: Config, args: argparse.Namespace) -> int:
    client = _make_client(cfg)
    user_id = client.resolve_user(cfg.user)
    statuses = args.status or None
    data: list = []
    for media in _media_list(args.media):
        data.extend(export_rates(client, user_id, statuses, media))
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Exported {len(data)} entries to {args.out}")
    else:
        print(text)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        from .web import run_server
    except ImportError as exc:
        print(f"Web dependencies missing ({exc}). Install with:  "
              f"pip install -e .[web]", file=sys.stderr)
        return 1
    run_server(host=args.host, port=args.port, env_file=args.env)
    return 0


def cmd_run(cfg: Config, args: argparse.Namespace) -> int:
    if not cfg.rules:
        print("No rules defined in config. Add [[rules]] sections.", file=sys.stderr)
        return 1

    client = _make_client(cfg)
    user_id = client.resolve_user(cfg.user)
    print(f"User id={user_id}\n")

    plan = build_plan(client, user_id, cfg.rules, log=print)
    print()

    if not plan:
        print("Nothing matches the rules. No changes.")
        return 0

    # Summary by media + source -> target.
    summary = Counter((m.rule.media, m.rule.source, m.rule.target) for m in plan)
    print("Planned moves:")
    for (media, source, target), n in sorted(summary.items()):
        print(f"  {media}: {source} -> {target}: {n}")
    print(f"  total: {len(plan)}\n")

    # Detailed listing (full list with --verbose, otherwise a short sample).
    sample = plan if args.verbose else plan[:args.sample]
    for m in sample:
        rating = "-" if m.rating is None else f"{m.rating:g}"
        print(f"  [{m.rule.media}:{m.rule.source}->{m.rule.target}] "
              f"progress={m.progress} rating={rating}  {m.title}")
    if not args.verbose and len(plan) > args.sample:
        print(f"  ... and {len(plan) - args.sample} more (use --verbose to list all)")
    print()

    if not args.apply:
        print("Dry run. Re-run with --apply to perform these moves.")
        return 0

    print("Applying...")
    done = 0
    for m in plan:
        try:
            client.update_status(m.rate["id"], m.rule.target)
            done += 1
        except ShikimoriError as exc:
            print(f"  failed for rate {m.rate['id']} ({m.title}): {exc}", file=sys.stderr)
        if done % 50 == 0 and done:
            print(f"  moved {done}/{len(plan)}")
    print(f"Done. Moved {done}/{len(plan)} entries.")
    return 0


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shikimori-manager",
        description="Move anime between your Shikimori lists using declarative rules.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-c", "--config", default="config.toml",
                        help="Path to the config file (default: config.toml).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_auth = sub.add_parser("auth", help="Obtain/refresh an OAuth token.")
    p_auth.add_argument("--code", help="Authorization code (skips the interactive prompt).")
    p_auth.set_defaults(func=cmd_auth)

    p_who = sub.add_parser("whoami", help="Show the user owning the current token.")
    p_who.set_defaults(func=cmd_whoami)

    media_choices = ("anime", "manga", "both")

    p_lists = sub.add_parser("lists", help="Show how many entries each list has.")
    p_lists.add_argument("--media", choices=media_choices, default="both")
    p_lists.set_defaults(func=cmd_lists)

    p_stats = sub.add_parser("stats", help="Show per-list aggregate statistics.")
    p_stats.add_argument("--media", choices=media_choices, default="both")
    p_stats.set_defaults(func=cmd_stats)

    p_export = sub.add_parser("export", help="Export your lists to JSON (backup).")
    p_export.add_argument("--status", action="append",
                          help="Limit to a status (repeatable). Default: all lists.")
    p_export.add_argument("--media", choices=media_choices, default="both")
    p_export.add_argument("-o", "--out", help="Write to a file instead of stdout.")
    p_export.set_defaults(func=cmd_export)

    p_run = sub.add_parser("run", help="Apply the move rules (dry run by default).")
    p_run.add_argument("--apply", action="store_true",
                       help="Actually perform the moves (omit for a dry run).")
    p_run.add_argument("--verbose", action="store_true",
                       help="List every planned move, not just a sample.")
    p_run.add_argument("--sample", type=int, default=20,
                       help="How many moves to preview in a dry run (default: 20).")
    p_run.set_defaults(func=cmd_run)

    p_serve = sub.add_parser("serve", help="Launch the web UI (requires .[web] extra).")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    p_serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000).")
    p_serve.add_argument("--env", default=".env", help="Path to the .env file (default: .env).")
    p_serve.set_defaults(func=cmd_serve, needs_config=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # The web UI manages its own env-based config, so it doesn't need a TOML file.
    if not getattr(args, "needs_config", True):
        return args.func(args)

    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:  # TOML parse / rule validation errors
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    try:
        return args.func(cfg, args)
    except ShikimoriError as exc:
        print(f"API error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
