"""CLI entry point: `python -m syndicate <command> [flags]`.

Implements the `devto` subcommand (publish/update posts to Dev.to), the
`linkedin` subcommand (preview/publish a personal-profile LinkedIn share),
and the pure, local `medium`/`teasers` generators (§3.1 of the plan). Draft
is the default for Dev.to (§3a of the plan): `published:true` requires an
explicit `--publish`, and `--dry-run` makes zero network calls. LinkedIn has
no draft state (§3.5 of `docs/plans/linkedin-syndication.md`): only
`--publish` makes a live call — the default and `--dry-run` are both
zero-network previews. `medium`/`teasers` never touch the network at all.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from syndicate.devto import DevToClient, DevToError
from syndicate.generate import (
    medium_checklist_snippets,
    medium_import_list,
    resolve_linkedin_commentary,
    teaser,
)
from syndicate.linkedin import LinkedInClient, LinkedInError
from syndicate.payload import build_devto_article, build_linkedin_share
from syndicate.posts import Post, load_posts
from syndicate.state import load_state, save_state

STATE_FILENAME = "state.json"
LINKEDIN_STATE_FILENAME = "linkedin_state.json"
SYNDICATION_DIRNAME = "syndication"
LINKEDIN_SIDECAR_DIRNAME = "linkedin"

LINKEDIN_NO_DRAFT_FOOTER = (
    "LinkedIn has no draft state; nothing was posted. "
    "Re-run with --publish to post live."
)


def _state_path() -> Path:
    return Path(__file__).resolve().parent / STATE_FILENAME


def _linkedin_state_path() -> Path:
    return Path(__file__).resolve().parent / LINKEDIN_STATE_FILENAME


def _linkedin_sidecar_dir() -> Path:
    """Anchor to the `syndicate` package's own directory
    (`scripts/syndicate/linkedin/`), matching how `_state_path()` anchors
    `linkedin_state.json` beside it. This is a committed, owner-authored
    sidecar dir — distinct from the gitignored `scripts/syndication/` output
    tree that `_syndication_dir()` below points at (plan §3.3.1: sidecars
    must live under the tracked package dir, not the regenerable one).
    """
    return Path(__file__).resolve().parent / LINKEDIN_SIDECAR_DIRNAME


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


def _confirm_live_publish(count: int, yes: bool, platform: str = "Dev.to") -> bool:
    """Return True if a `--publish` live run should proceed. `--yes` skips
    the prompt outright. Otherwise: interactively confirm on a TTY, or
    refuse outright on a non-interactive stream (no silent auto-publish).

    `platform` names the target in the confirmation prompt; it defaults to
    `"Dev.to"` so `cmd_devto`'s existing call sites (which don't pass it) are
    byte-for-byte unchanged. `cmd_linkedin` passes `platform="LinkedIn"`.
    """
    if yes:
        return True

    if not sys.stdin.isatty():
        print(
            "Refusing to publish live in a non-interactive session without "
            "confirmation. Re-run with --yes to confirm."
        )
        return False

    print(f"About to publish {count} post(s) to {platform}. WILL PUBLISH LIVE.")
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


def _linkedin_commentary_source(post: Post, sidecar_dir: Path) -> str:
    """`"sidecar"` if a non-empty `<slug>.md` override exists in
    `sidecar_dir`, else `"generated"` (the `_linkedin_hook` fallback). Mirrors
    the precedence check inside `generate.resolve_linkedin_commentary` —
    display-only, so the CLI can label which source a preview/publish used.
    """
    sidecar_path = sidecar_dir / f"{post.slug}.md"
    if sidecar_path.is_file() and sidecar_path.read_text(encoding="utf-8").strip():
        return "sidecar"
    return "generated"


def _preview_author_urn() -> str:
    """The author URN to render *preview* text with: the `LINKEDIN_AUTHOR_URN`
    env value if the owner has set it (reading it is not a network call),
    else a clear placeholder. Preview never calls the network, so this must
    never call `client.get_person_urn()`.
    """
    return os.environ.get("LINKEDIN_AUTHOR_URN") or "urn:li:person:<resolved-at-publish-time>"


def _print_linkedin_preview(post: Post, sidecar_dir: Path, author_urn: str) -> None:
    source = _linkedin_commentary_source(post, sidecar_dir)
    commentary = resolve_linkedin_commentary(post, sidecar_dir)
    payload = build_linkedin_share(post, author_urn, commentary)
    content = payload["specificContent"]["com.linkedin.ugc.ShareContent"]
    visibility = payload["visibility"]["com.linkedin.ugc.MemberNetworkVisibility"]
    print(f"[{post.slug}] author={author_urn} visibility={visibility} source={source}")
    print(content["shareCommentary"]["text"])
    print()


def cmd_linkedin(args: argparse.Namespace) -> int:
    posts = _select_posts(load_posts(), args.only)

    if not posts:
        print("No posts selected.")
        return 0

    sidecar_dir = _linkedin_sidecar_dir()

    # Key divergence from devto (§3.5): LinkedIn has no draft state, so
    # anything short of an explicit `--publish` — including the default with
    # neither flag — is a zero-network preview. `--dry-run` always forces a
    # preview even alongside `--publish` (mirrors devto's own --dry-run
    # precedence), so a `--publish --dry-run` combination can never post.
    if args.dry_run or not args.publish:
        author_urn = _preview_author_urn()
        for post in posts:
            _print_linkedin_preview(post, sidecar_dir, author_urn)
        print(LINKEDIN_NO_DRAFT_FOOTER)
        return 0

    client = LinkedInClient()
    if not client.has_token:
        print(
            "LINKEDIN_ACCESS_TOKEN is not set — cannot make live LinkedIn calls. "
            "Set the LINKEDIN_ACCESS_TOKEN environment variable, or omit "
            "--publish to preview."
        )
        return 1

    if not _confirm_live_publish(len(posts), args.yes, platform="LinkedIn"):
        return 1

    state_path = _linkedin_state_path()
    state = load_state(state_path)

    # Resolved lazily, on the first post that actually needs to be shared
    # (not eagerly before the skip check) — a batch that is entirely
    # already-shared makes zero `get_person_urn` calls. Once resolved it is
    # cached in this local for the rest of the run (§3.5: "once per run").
    author_urn = os.environ.get("LINKEDIN_AUTHOR_URN")

    shared = 0
    skipped_already = 0
    failed = 0

    for post in posts:
        existing_urn = state.get(post.slug)
        if existing_urn is not None:
            skipped_already += 1
            print(f"[{post.slug}] already shared (urn={existing_urn})")
            continue

        if not author_urn:
            author_urn = client.get_person_urn()

        commentary = resolve_linkedin_commentary(post, sidecar_dir)
        payload = build_linkedin_share(post, author_urn, commentary)

        try:
            urn = client.create_ugc_post(payload)
        except (LinkedInError, RuntimeError) as exc:
            # Both a non-2xx (LinkedInError) and a malformed-success 201
            # missing X-RestLi-Id (RuntimeError — see linkedin.py) are a
            # failed post, not a batch-aborting error: state stays clean
            # since it is only written after a confirmed URN below.
            failed += 1
            print(f"[{post.slug}] FAILED: {exc}")
            continue

        state[post.slug] = urn
        save_state(state_path, state)
        shared += 1
        print(f"[{post.slug}] shared (urn={urn})")

    print(f"\nShared: {shared}, skipped(already): {skipped_already}, failed: {failed}.")
    return 0


def cmd_medium(args: argparse.Namespace) -> int:
    posts = load_posts()

    output_dir = _syndication_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "medium-import-list.md"
    output_path.write_text(medium_import_list(posts))
    print(f"Wrote {output_path} ({len(posts)} post(s)).")

    checklists_dir = output_dir / "medium-checklists"
    checklist_count = 0
    for post in posts:
        snippet = medium_checklist_snippets(post)
        if not snippet:
            continue
        checklists_dir.mkdir(parents=True, exist_ok=True)
        (checklists_dir / f"{post.slug}.md").write_text(snippet)
        checklist_count += 1

    print(f"Wrote {checklist_count} Medium checklist file(s) to {checklists_dir}/.")
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

    linkedin_parser = subparsers.add_parser(
        "linkedin", help="Preview/publish a personal-profile LinkedIn share per post"
    )
    linkedin_selection = linkedin_parser.add_mutually_exclusive_group()
    linkedin_selection.add_argument(
        "--all", action="store_true", help="Select all posts (default)"
    )
    linkedin_selection.add_argument(
        "--only", metavar="NN[,NN,...]", help="Select posts by numeric filename prefix"
    )
    linkedin_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the resolved share; make no network calls",
    )
    linkedin_parser.add_argument(
        "--publish",
        action="store_true",
        help="Make the live create_ugc_post call (default: preview only, no draft state)",
    )
    linkedin_parser.add_argument(
        "--yes", action="store_true", help="Skip the interactive live-publish confirmation"
    )
    linkedin_parser.set_defaults(func=cmd_linkedin)

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
