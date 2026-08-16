#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import requests

from config import Config, DEFAULT_CONFIG
from parser import WikiHowParser
from render import WikiHowRenderer
from scraper import WikiHowScraper
from sitemap import WikiHowSitemap


class WikiHowCLI:
    def __init__(self, settings: Config = DEFAULT_CONFIG) -> None:
        self.settings = settings
        self.parser = WikiHowParser(settings)
        self.scraper = WikiHowScraper(settings)
        self.renderer = WikiHowRenderer(settings)
        self.sitemap = WikiHowSitemap(settings)

    # public api
    def run(self, argv: list[str] | None = None) -> int:
        argv = list(sys.argv[1:] if argv is None else argv)
        args = self._build_arg_parser().parse_args(argv)

        if args.command == "fetch":
            urls = list(args.urls)

            if args.from_file:
                if not args.from_file.is_file():
                    print(f"url file not found: {args.from_file}", file=sys.stderr)
                    return 2

                urls.extend(self._read_url_file(args.from_file))

            if not urls:
                print("fetch needs URLs or --from-file", file=sys.stderr)
                return 2

            skipped = self.scraper.fetch_urls(urls, args.cache_dir, args.delay)

            return 1 if skipped else 0

        if args.command == "update":
            tokens = tuple(
                word.strip()
                for word in args.tokens.split(",")
                if word.strip()
            )

            if not tokens and not args.all:
                print("update needs --tokens or --all", file=sys.stderr)
                return 2

            return self.run_update(
                args.cache_dir,
                args.state,
                tokens,
                args.delay,
                args.limit,
                args.dry_run,
            )

        if not args.cache_dir.is_dir():
            print(f"cache dir not found: {args.cache_dir}", file=sys.stderr)
            return 2

        integrity_failures = self.run_parse(args.cache_dir, args.out_dir)

        return 1 if integrity_failures else 0

    def run_parse(self, cache_dir: Path, out_dir: Path) -> list[str]:
        json_dir = out_dir / "json"
        md_dir = out_dir / "md"
        json_dir.mkdir(parents=True, exist_ok=True)
        md_dir.mkdir(parents=True, exist_ok=True)

        integrity_failures: list[str] = []

        for html_path in sorted(cache_dir.glob("*.html")):
            loaded = self.scraper.load_verified(html_path)

            if loaded is None:
                integrity_failures.append(html_path.stem)
                continue

            raw, meta = loaded
            slug = html_path.stem

            article = self.parser.parse_article(
                raw,
                url=meta["url"],
                retrieved=meta["retrieved_utc"],
                raw_sha256=meta["sha256"],
                robots_ok=meta["robots"],
                slug=slug,
            )

            json_text = json.dumps(article, indent=2, ensure_ascii=False)
            md_text = self.renderer.render_markdown(article)

            (json_dir / f"{slug}.json").write_text(json_text, encoding="utf-8")
            (md_dir / f"{slug}.md").write_text(md_text, encoding="utf-8")

        return integrity_failures

    def run_update(
        self,
        cache_dir: Path,
        state_path: Path,
        tokens: tuple[str, ...],
        delay_seconds: float,
        limit: int,
        dry_run: bool,
    ) -> int:
        try:
            previous = self.sitemap.load_snapshot(state_path)
        except ValueError as error:
            print(f"{error}; update aborted", file=sys.stderr)
            return 2

        try:
            current = self.sitemap.download(delay_seconds)
        except (requests.RequestException, ValueError) as error:
            print(f"sitemap download failed: {error}", file=sys.stderr)
            return 2

        if not current:
            print("sitemap is empty", file=sys.stderr)
            return 2

        _, changed, _ = self.sitemap.diff_snapshot(previous, current)
        selected = set(self.sitemap.select(list(current), tokens))

        stale = [url for url in changed if url in selected]
        missing = [
            url
            for url in sorted(selected)
            if not self.scraper.archive_path(url, cache_dir).exists()
        ]
        pending = sorted(set(stale) | set(missing))
        to_fetch = pending[:limit] if limit else pending

        if dry_run:
            for url in to_fetch[:10]:
                print(f"  would fetch {url}")
            return 0

        for url in set(stale) & set(to_fetch):
            self._purge(url, cache_dir)

        skipped = self.scraper.fetch_urls(to_fetch, cache_dir, delay_seconds)

        if skipped:
            print(
                f"{len(skipped)} fetches failed; snapshot not updated",
                file=sys.stderr,
            )
            return 1

        if len(to_fetch) < len(pending):
            print("snapshot not updated; selected updates remain pending")
            return 0

        self.sitemap.save_snapshot(state_path, self.sitemap.merge_snapshot(previous, current))

        return 0

    # helpers
    def _purge(self, url: str, cache_dir: Path) -> None:
        html_path = self.scraper.archive_path(url, cache_dir)
        html_path.unlink(missing_ok=True)
        html_path.with_suffix(".meta.json").unlink(missing_ok=True)

    @staticmethod
    def _non_negative_int(text: str) -> int:
        value = int(text)

        if value < 0:
            raise argparse.ArgumentTypeError(f"must be 0 or greater, got {value}")

        return value

    @staticmethod
    def _non_negative_float(text: str) -> float:
        value = float(text)

        if value < 0:
            raise argparse.ArgumentTypeError(f"must be 0 or greater, got {value}")

        return value

    @staticmethod
    def _read_url_file(path: Path) -> list[str]:
        return [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def _build_arg_parser(self) -> argparse.ArgumentParser:
        arg_parser = argparse.ArgumentParser(description="wikiHow scraper")
        subparsers = arg_parser.add_subparsers(dest="command", required=True)

        fetch = subparsers.add_parser("fetch", help="fetch pages into the cache")
        fetch.add_argument("urls", nargs="*")
        fetch.add_argument("--from-file", type=Path, help="one URL per line")
        fetch.add_argument("--delay", type=self._non_negative_float, default=self.settings.default_delay_seconds)
        fetch.add_argument("--cache-dir", type=Path, default=Path("out/html"))

        parse_cmd = subparsers.add_parser("parse", help="parse the cache to JSON/Markdown")
        parse_cmd.add_argument("--cache-dir", type=Path, default=Path("out/html"))
        parse_cmd.add_argument("--out-dir", type=Path, default=Path("out"))

        update = subparsers.add_parser("update", help="diff the sitemap and fetch what is new")
        update.add_argument("--cache-dir", type=Path, default=Path("out/html"))
        update.add_argument("--state", type=Path, default=Path("state/sitemap.json"))
        update.add_argument("--tokens", default="", help="exact slug tokens, comma separated")
        update.add_argument("--delay", type=self._non_negative_float, default=self.settings.default_delay_seconds)
        update.add_argument("--limit", type=self._non_negative_int, default=0, help="0 means no cap")
        update.add_argument("--dry-run", action="store_true")
        update.add_argument("--all", action="store_true", help="fetch without a token filter")

        return arg_parser

if __name__ == "__main__":
    sys.exit(WikiHowCLI().run())
