import json
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path

import requests

from config import Config, DEFAULT_CONFIG
from schemas import VerifiedMeta
from utils import sha256_hex, url_slug, utc_now


class WikiHowScraper:
    def __init__(self, settings: Config = DEFAULT_CONFIG) -> None:
        self.settings = settings
        self._robots_parsers: dict[
            str,
            urllib.robotparser.RobotFileParser | None,
        ] = {}

    # public api
    @staticmethod
    def archive_path(url: str, cache_dir: Path) -> Path:
        return cache_dir / f"{url_slug(url)}.html"

    def fetch_urls(self, urls: list[str], cache_dir: Path, delay_seconds: float) -> list[str]:
        cache_dir.mkdir(parents=True, exist_ok=True)

        skipped: list[str] = []

        with requests.Session() as session:
            session.headers["User-Agent"] = self.settings.user_agent

            for url in urls:
                verdict = self._robots_status(url, session)

                if verdict == "no":
                    print(f"SKIP (robots.txt disallows): {url}")
                    skipped.append(url)
                    continue

                html_path = self.archive_path(url, cache_dir)

                if html_path.exists():
                    print(f"cached: {html_path.stem}")
                    continue

                # delay after every network attempt, success or failure
                try:
                    response = session.get(url, timeout=30)
                    response.raise_for_status()
                except requests.RequestException as error:
                    print(f"FAIL {url}: {error}")
                    skipped.append(url)
                else:
                    self._archive_response(
                        response,
                        url,
                        verdict,
                        cache_dir,
                    )
                finally:
                    time.sleep(delay_seconds)

        return skipped

    def load_verified(self, html_path: Path) -> tuple[bytes, VerifiedMeta] | None:
        raw = html_path.read_bytes()
        digest = sha256_hex(raw)
        meta_path = html_path.with_suffix(".meta.json")

        if meta_path.exists():
            try:
                sidecar = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                print(f"BAD METADATA {meta_path.name}, page skipped ({error})")
                return None

            if not isinstance(sidecar, dict):
                print(
                    f"BAD METADATA {meta_path.name}, page skipped "
                    f"(expected an object, found {type(sidecar).__name__})"
                )
                return None
        else:
            sidecar = {}

        recorded = sidecar.get("sha256", sidecar.get("sha256_raw_html"))
        robots = sidecar.get("robots", sidecar.get("robots_ok", "unknown"))

        if recorded is not None and recorded != digest:
            print(
                f"INTEGRITY FAIL {html_path.stem}: archive digest "
                f"{digest[:12]} != recorded {recorded[:12]}, page skipped"
            )
            return None

        return raw, {
            "url": sidecar.get("url", f"file://{html_path}"),
            "retrieved_utc": sidecar.get("retrieved_utc"),
            "sha256": digest,
            "robots": robots,
        }

    # helpers
    def _robots_status(self, url: str, session: requests.Session) -> str:
        parts = urllib.parse.urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"

        if host not in self._robots_parsers:
            parser = urllib.robotparser.RobotFileParser()

            try:
                response = session.get(f"{host}/robots.txt", timeout=30)
                response.raise_for_status()
                parser.parse(response.text.splitlines())
            except requests.RequestException:
                self._robots_parsers[host] = None
            else:
                self._robots_parsers[host] = parser

        parser = self._robots_parsers[host]

        if parser is None:
            return "unknown"

        return "yes" if parser.can_fetch(self.settings.user_agent, url) else "no"
    
    def _archive_response(
        self,
        response: requests.Response,
        requested_url: str,
        robots_verdict: str,
        cache_dir: Path,
    ) -> None:
        final_url = str(response.url)
        slug = url_slug(final_url)
        html_path = cache_dir / f"{slug}.html"

        if html_path.exists():
            print(f"cached (via redirect): {slug}")
            return

        raw = response.content
        html_path.write_bytes(raw)

        meta = {
            "url": final_url,
            "requested_url": requested_url,
            "retrieved_utc": utc_now(),
            "sha256": sha256_hex(raw),
            "status": response.status_code,
            "robots": robots_verdict,
        }

        html_path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        print(f"fetched: {slug} ({len(raw)} bytes)")

