"""CLI entry point: `python -m syndicate <command> [flags]`.

Implements the `devto` subcommand (publish/update posts to Dev.to) and the
pure, local `medium`/`teasers` generators (§3.1 of the plan). Draft is the
default (§3a of the plan): `published:true` requires an explicit `--publish`,
and `--dry-run` makes zero network calls. `medium`/`teasers` never touch the
network at all.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from syndicate.devto import DevToClient, DevToError
from syndicate.generate import medium_import_list, teaser
from syndicate.payload import build_devto_article
from syndicate.posts import Post, load_posts
from syndicate.state import load_state, save_state

STATE_FILENAME = "state.json"
SYNDICATION_DIRNAME = "syndication"


def _state_path() -> Path:
    return Path(__file__).resolve().parent / STATE_FILENAME


def _syndication_dir() -> Path:
    """Anchor to the `syndicate` package's parent directory (`scripts/`),
    not the caller's cwd — so `medium`/`teasers` land in the same place
    (`scripts/syndication/`) regardless of where the CLI is invoked from,
    matching how `state.json` is anchored above.
    """
    return Path(__file__).resolve().parent.parent / SYNDICATION_DIRNAME


def _select_posts(posts: list[Post], only: str | None) -> list[Post]:
    """`--all` (default, when `only` is falsy) returns every post; `--only
    NN[,NN,...]` filters to posts whose numeric filename prefix matches.
    """
    if not only:
        return posts
    wanted = {n.strip() for n in only.split(",") if n.strip()}
    return [post for post in posts if post.slug.split("-", 1)[0] in wanted]


def _print_dry_run(post: Post, article: dict, state: dict) -> None:
    action = "update" if post.slug in state else "create"
    print(
        f"[{post.slug}] action={action} published={article['published']} "
        f"tags={article['tags']} canonical={article['canonical_url']} "
        f"body_len={len(article['body_markdown'])}"
    )


def _confirm_live_publish(count: int, yes: bool) -> bool:
    """Return True if a `--publish` live run should proceed. `--yes` skips
    the prompt outright. Otherwise: interactively confirm on a TTY, or
    refuse outright on a non-interactive stream (no silent auto-publish).
    """
    if yes:
        return True

    if not sys.stdin.isatty():
        print(
            "Refusing to publish live in a non-interactive session without "
            "confirmation. Re-run with --yes to confirm."
        )
        return False

    print(f"About to publish {count} post(s) to Dev.to. WILL PUBLISH LIVE.")
    answer = input("Proceed? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return False
    return True


def cmd_devto(args: argparse.Namespace) -> int:
    posts = _select_posts(load_posts(), args.only)

    if not posts:
        print("No posts selected.")
        return 0

    articles = [(post, build_devto_article(post, publish=args.publish)) for post in posts]

    state_path = _state_path()
    state = load_state(state_path)

    if args.dry_run:
        for post, article in articles:
            _print_dry_run(post, article, state)
        print(f"\nDry run: {len(articles)} post(s) would be sent, 0 network calls made.")
        return 0

    client = DevToClient()
    if not client.has_key:
        print(
            "DEVTO_API_KEY is not set — cannot make live Dev.to calls. "
            "Set the DEVTO_API_KEY environment variable, or pass --dry-run."
        )
        return 1

    if args.publish and not _confirm_live_publish(len(articles), args.yes):
        return 1

    existing_by_canonical: dict[str, int] | None = None
    created = 0
    updated = 0
    skipped = 0

    for post, article in articles:
        article_id = state.get(post.slug)

        if article_id is None:
            if existing_by_canonical is None:
                existing_by_canonical = {
                    a["canonical_url"]: a["id"]
                    for a in client.list_my_articles()
                    if a.get("canonical_url")
                }
            article_id = existing_by_canonical.get(post.canonical_url)

        try:
            if article_id is not None:
                client.update_article(article_id, article)
                state[post.slug] = article_id
                save_state(state_path, state)
                updated += 1
                print(f"[{post.slug}] updated (id={article_id})")
            else:
                result = client.create_article(article)
                new_id = result["id"]
                state[post.slug] = new_id
                save_state(state_path, state)
                created += 1
                print(f"[{post.slug}] created (id={new_id})")
        except DevToError as exc:
            skipped += 1
            print(f"[{post.slug}] FAILED: {exc}")

    print(f"\nSummary: {created} created, {updated} updated, {skipped} skipped.")
    return 0


def cmd_medium(args: argparse.Namespace) -> int:
    posts = load_posts()

    output_dir = _syndication_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "medium-import-list.md"
    output_path.write_text(medium_import_list(posts))

    print(f"Wrote {output_path} ({len(posts)} post(s)).")
    return 0


def cmd_teasers(args: argparse.Namespace) -> int:
    posts = load_posts()

    output_dir = _syndication_dir() / "teasers"
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for post in posts:
        output_path = output_dir / f"{post.slug}.md"
        output_path.write_text(teaser(post))
        count += 1

    print(f"Wrote {count} teaser file(s) to {output_dir}/.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="syndicate")
    subparsers = parser.add_subparsers(dest="command", required=True)

    devto_parser = subparsers.add_parser("devto", help="Publish/update posts to Dev.to")
    selection = devto_parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="Select all posts (default)")
    selection.add_argument(
        "--only", metavar="NN[,NN,...]", help="Select posts by numeric filename prefix"
    )
    devto_parser.add_argument(
        "--dry-run", action="store_true", help="Print payloads; make no network calls"
    )
    devto_parser.add_argument(
        "--publish", action="store_true", help="Set published:true (default: draft)"
    )
    devto_parser.add_argument(
        "--yes", action="store_true", help="Skip the interactive live-publish confirmation"
    )
    devto_parser.set_defaults(func=cmd_devto)

    medium_parser = subparsers.add_parser(
        "medium", help="Write the Medium import checklist (syndication/medium-import-list.md)"
    )
    medium_parser.set_defaults(func=cmd_medium)

    teasers_parser = subparsers.add_parser(
        "teasers", help="Write per-post LinkedIn/Reddit/HN teasers (syndication/teasers/)"
    )
    teasers_parser.set_defaults(func=cmd_teasers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
