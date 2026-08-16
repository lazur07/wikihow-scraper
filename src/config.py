import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    # fetching
    user_agent: str = "wikihow-scrape/1.1 (academic research, non-commercial)"
    default_delay_seconds: float = 3.0
    sitemap_index: str = "https://www.wikihow.com/sitemap_index.xml"

    # parsing
    html_parser: str = "html.parser"
    numbered_kinds: tuple[str, ...] = ("method", "part")
    list_sections: tuple[tuple[str, str], ...] = (
        ("tips", "t"),
        ("warnings", "w"),
    )

    label_selectors: tuple[str, ...] = (
        ".method_label",
        ".altblock",
        ".headline_label",
        ".method_number",
    )

    headline_selectors: tuple[str, ...] = (
        ".mw-headline",
        ".section_head",
        "h3",
    )

    junk_selectors: tuple[str, ...] = (
        "script",
        "style",
        "noscript",
        "sup.reference",
        ".mw-editsection",
        ".step_num",
        ".stepanchor",
        ".image_details",
        ".mwimg",
        "video",
        ".video-container",
        ".vid-container",
        ".embedvideocontainer",
        ".ad_label",
        ".wh_ad_inner",
        ".wh_ad",
        "table",
        '[class*="wh_thumb"]',
        '[class*="wh_vote"]',
        ".qa_widget_vote_links",
        ".qa_widget_vote_buttons",
    )

    artifact_patterns: tuple[re.Pattern[str], ...] = (
        re.compile(r"X\s+(?:Trustworthy|Research|Expert)\s+[Ss]ource\b[^.]*?(?=\s|$)"),
        re.compile(r"\[\d+\]"),
        re.compile(r"\s*\bAdvertisement\b"),
        re.compile(r"\s*Thanks!?(?:\s+(?:Not\s+)?Helpful\s+\d+)+"),
    )

    method_prefix: re.Pattern[str] = re.compile(r"^\s*(?:Part|Method|Section)\s+\d+\s*(?:of\s+\d+)?\s*:?\s*", flags=re.IGNORECASE)


DEFAULT_CONFIG = Config()
