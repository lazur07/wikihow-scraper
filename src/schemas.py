from typing import TypedDict


class StepRecord(TypedDict):
    sid: str
    ordinal: int
    instruction: str
    elaboration: str
    details: list[str]


class MethodRecord(TypedDict):
    index: int
    kind: str
    title: str
    steps: list[StepRecord]


class ListItem(TypedDict):
    id: str
    ordinal: int
    text: str


class SourceRecord(TypedDict):
    url: str
    retrieved_utc: str
    sha256_raw_html: str
    robots: str


class TaskRecord(TypedDict):
    source_title: str
    source_slug: str


class ArticleRecord(TypedDict):
    source: SourceRecord
    task: TaskRecord
    methods: list[MethodRecord]
    tips: list[ListItem]
    warnings: list[ListItem]


class VerifiedMeta(TypedDict):
    url: str
    retrieved_utc: str | None
    sha256: str
    robots: str


class SnapshotEntry(TypedDict):
    lastmod: str | None
    active: bool
