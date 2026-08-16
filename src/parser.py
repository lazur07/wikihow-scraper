import re
import urllib.parse

from bs4 import BeautifulSoup
from bs4.element import Tag

from config import Config, DEFAULT_CONFIG
from schemas import ArticleRecord, ListItem, MethodRecord, StepRecord
from utils import sha256_hex, url_slug, utc_now


class WikiHowParser:
    def __init__(self, settings: Config = DEFAULT_CONFIG) -> None:
        self.settings = settings

    # public api
    def parse_article(
        self,
        html: str | bytes,
        url: str,
        *,
        retrieved: str | None = None,
        raw_sha256: str | None = None,
        robots_ok: str = "unknown",
        slug: str | None = None,
    ) -> ArticleRecord:
        data = html if isinstance(html, bytes) else html.encode("utf-8")
        digest = raw_sha256 or sha256_hex(data)

        soup = BeautifulSoup(html, self.settings.html_parser)

        heading = soup.select_one("h1#section_0") or soup.find("h1")
        raw_title = (
            self._clean_text(heading.get_text(" ", strip=True))
            if heading
            else ""
        )

        last_segment = url.rsplit("/", 1)[-1]
        fallback_title = urllib.parse.unquote(last_segment).replace("-", " ")

        title = self._task_title(raw_title or fallback_title)

        return {
            "source": {
                "url": url,
                "retrieved_utc": retrieved or utc_now(),
                "sha256_raw_html": digest,
                "robots": robots_ok,
            },
            "task": {
                "source_title": title,
                "source_slug": slug or url_slug(url),
            },
            "methods": self._parse_step_sections(soup),
            "tips": self._parse_list_section(soup, "tips", "t"),
            "warnings": self._parse_list_section(soup, "warnings", "w"),
        }

    # text normalization
    def _clean_text(self, text: str) -> str:
        for pattern in self.settings.artifact_patterns:
            text = pattern.sub(" ", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"([.!?])\s+[.!?]", r"\1", text)
        return re.sub(r"\s+([,.;:!?])", r"\1", text).strip()

    @staticmethod
    def _task_title(title: str) -> str:
        return re.sub(r"^how to\s+", "", title.strip(), flags=re.IGNORECASE)

    # HTML helpers
    def _strip_junk(self, node: Tag) -> BeautifulSoup:
        fragment = BeautifulSoup(str(node), self.settings.html_parser)
        for selector in self.settings.junk_selectors:
            for junk in fragment.select(selector):
                junk.decompose()
        return fragment

    @staticmethod
    def _select_first(node: Tag, selectors: tuple[str, ...]) -> Tag | None:
        for selector in selectors:
            if element := node.select_one(selector):
                return element
        return None

    # method and step parsing
    def _method_kind_and_title(self, section: Tag) -> tuple[str, str]:
        headline = self._select_first(section, self.settings.headline_selectors)
        raw = (
            self._clean_text(headline.get_text(" ", strip=True))
            if headline
            else ""
        )

        label = self._select_first(section, self.settings.label_selectors)
        label_text = (
            self._clean_text(label.get_text(" ", strip=True))
            if label
            else ""
        )

        match = re.search(r"\b(Part|Method|Section)\s+\d+", f"{label_text} {raw}", flags=re.IGNORECASE)

        kind = match.group(1).lower() if match else "single"
        title = raw

        while (
            stripped := self.settings.method_prefix.sub("", title, count=1)
        ) != title:
            title = stripped

        return kind, title.strip()

    def _extract_details(self, fragment: BeautifulSoup) -> list[str]:
        details: list[str] = []

        for sublist in fragment.find_all(["ul", "ol"]):
            for bullet in sublist.find_all("li"):
                text = self._clean_text(bullet.get_text(" ", strip=True))
                if text:
                    details.append(text)
            sublist.decompose()

        return details

    def _extract_headline(self, fragment: BeautifulSoup) -> str:
        bold = fragment.select_one("b.whb") or fragment.find("b")

        if bold is None:
            return ""

        headline = self._clean_text(bold.get_text(" ", strip=True))
        bold.decompose()
        return headline

    def _parse_step_item(self, item: Tag, method_index: int, ordinal: int) -> StepRecord:
        fragment = self._strip_junk(item.select_one("div.step") or item)

        details = self._extract_details(fragment)
        headline = self._extract_headline(fragment)
        prose = self._clean_text(fragment.get_text(" ", strip=True))

        return {
            "sid": f"m{method_index}s{ordinal}",
            "ordinal": ordinal,
            "instruction": headline or prose,
            "elaboration": prose if headline else "",
            "details": details,
        }

    def _parse_step_sections(self, soup: BeautifulSoup) -> list[MethodRecord]:
        sections = soup.select("div.section.steps")

        if not sections:
            sections = [
                parent
                for ol in soup.select("ol.steps_list_2")
                if isinstance(parent := ol.parent, Tag)
            ]

        methods: list[MethodRecord] = []

        for method_index, section in enumerate(sections, start=1):
            kind, title = self._method_kind_and_title(section)
            step_lists = (
                section.select("ol.steps_list_2")
                or section.find_all("ol")
            )

            items = [
                item
                for step_list in step_lists
                for item in step_list.find_all("li", recursive=False)
            ]

            steps = [
                self._parse_step_item(item, method_index, ordinal)
                for ordinal, item in enumerate(items, start=1)
            ]

            if steps:
                methods.append(
                    {
                        "index": method_index,
                        "kind": kind,
                        "title": title,
                        "steps": steps,
                    }
                )

        return methods

    def _parse_list_section(self, soup: BeautifulSoup, section_key: str, id_prefix: str) -> list[ListItem]:
        section = (
            soup.find(id=section_key)
            or soup.find(id=re.compile(f"^{section_key}", re.IGNORECASE))
            or soup.select_one(f"div.section.{section_key}")
        )

        if not isinstance(section, Tag):
            return []

        items: list[ListItem] = []
        seen: set[str] = set()

        for bullet in section.select("ul li"):
            fragment = self._strip_junk(bullet)
            text = self._clean_text(fragment.get_text(" ", strip=True))

            if text and text not in seen:
                seen.add(text)
                ordinal = len(items) + 1
                items.append(
                    {
                        "id": f"{id_prefix}{ordinal}",
                        "ordinal": ordinal,
                        "text": text,
                    }
                )

        return items

