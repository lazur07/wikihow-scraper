import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from config import Config, DEFAULT_CONFIG
from schemas import SnapshotEntry


class WikiHowSitemap:
    def __init__(self, settings: Config = DEFAULT_CONFIG) -> None:
        self.settings = settings

    # public api
    # a partial registry would read as mass deletion,
    # so this fails closed
    def download(self, delay_seconds: float, index_url: str | None = None) -> dict[str, str | None]:
        with requests.Session() as session:
            session.headers["User-Agent"] = self.settings.user_agent

            entry_point = index_url or self.settings.sitemap_index
            kind, entries = self._get(session, entry_point)

            if kind == "urlset":
                return entries

            urls: dict[str, str | None] = {}

            for index, part in enumerate(entries):
                if index:
                    time.sleep(delay_seconds)

                part_kind, part_entries = self._get(session, part)

                if part_kind != "urlset":
                    raise ValueError(f"expected a urlset: {part}")

                urls.update(part_entries)

        return urls

    @staticmethod
    def select(urls: list[str], tokens: tuple[str, ...]) -> list[str]:
        if not tokens:
            return sorted(urls)

        wanted = {token.lower() for token in tokens}
        return sorted(url for url in urls if wanted & set(WikiHowSitemap._slug_tokens(url)))

    # snapshot management
    # a missing snapshot means "nothing synced yet"; an unreadable one means we
    # do not know what is synced, and treating that as empty would re-diff the
    # whole corpus against nothing
    @staticmethod
    def load_snapshot(path: Path) -> dict[str, SnapshotEntry]:
        if not path.exists():
            return {}

        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError(f"corrupt snapshot {path}: {error}") from error

        if not isinstance(snapshot, dict):
            raise ValueError(
                f"corrupt snapshot {path}: expected an object, "
                f"found {type(snapshot).__name__}"
            )

        return snapshot

    @staticmethod
    def save_snapshot(path: Path, snapshot: dict[str, SnapshotEntry]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def merge_snapshot(previous: dict[str, SnapshotEntry], current: dict[str, str | None]) -> dict[str, SnapshotEntry]:
        # urls that vanished stay on record, flagged inactive
        merged = {
            url: {**entry, "active": url in current}
            for url, entry in previous.items()
        }

        for url, lastmod in current.items():
            merged[url] = {
                **previous.get(url, {}),
                "lastmod": lastmod,
                "active": True,
            }

        return merged

    @staticmethod
    def diff_snapshot(previous: dict[str, SnapshotEntry], current: dict[str, str | None]) -> tuple[list[str], list[str], list[str]]:
        added = [url for url in current if url not in previous]
        changed = [
            url
            for url, lastmod in current.items()
            if url in previous and previous[url].get("lastmod") != lastmod
        ]
        removed = [
            url
            for url, entry in previous.items()
            if url not in current and entry.get("active", True)
        ]
        return sorted(added), sorted(changed), sorted(removed)


    # sitemap parsing
    def _get(self, session: requests.Session, url: str) -> tuple[str, dict[str, str | None]]:
        response = session.get(url, timeout=60)
        response.raise_for_status()

        kind, entries = self._parse_sitemap(response.text)

        if kind == "invalid":
            raise ValueError(f"invalid sitemap: {url}")

        return kind, entries

    @staticmethod
    def _parse_sitemap(xml_text: str) -> tuple[str, dict[str, str | None]]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return "invalid", {}

        kind = WikiHowSitemap._local_tag(root)

        if kind not in ("sitemapindex", "urlset"):
            return "invalid", {}

        entries: dict[str, str | None] = {}

        for node in root:
            loc: str | None = None
            lastmod: str | None = None

            for child in node:
                tag = WikiHowSitemap._local_tag(child)

                if tag == "loc" and child.text:
                    loc = child.text.strip()
                elif tag == "lastmod" and child.text:
                    lastmod = child.text.strip()

            if loc:
                entries[loc] = lastmod

        return kind, entries

    @staticmethod
    def _local_tag(element: ET.Element) -> str:
        return element.tag.rsplit("}", 1)[-1]

    # url helpers
    @staticmethod
    def _slug_tokens(url: str) -> list[str]:
        slug = urllib.parse.unquote(url.rstrip("/").rsplit("/", 1)[-1])
        return [token.lower() for token in slug.split("-") if token]
