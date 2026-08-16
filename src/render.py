from config import Config, DEFAULT_CONFIG
from schemas import ArticleRecord, MethodRecord


class WikiHowRenderer:
    def __init__(self, settings: Config = DEFAULT_CONFIG) -> None:
        self.settings = settings

    def render_markdown(self, article: ArticleRecord) -> str:
        blocks = [
            f"# {article['task']['source_title']}\n"
            f"Source: {article['source']['url']}"
        ]

        # methods and steps
        for method in article["methods"]:
            heading = self._method_heading(method)
            lines = [heading] if heading else []

            for step in method["steps"]:
                prose = " ".join(
                    part
                    for part in (step["instruction"], step["elaboration"])
                    if part
                )

                lines.append(f"{step['ordinal']}. {prose}")
                lines.extend(f"   * {detail}" for detail in step["details"])

            if lines:
                blocks.append("\n".join(lines))

        # tips and warnings
        for section_key, _ in self.settings.list_sections:
            items = article[section_key]

            if items:
                blocks.append(
                    "\n".join(
                        [
                            f"## {section_key.capitalize()}",
                            *(f"- {item['text']}" for item in items),
                        ]
                    )
                )

        return "\n\n".join(blocks) + "\n"

    def _method_heading(self, method: MethodRecord) -> str:
        title = method["title"]

        if method["kind"] in self.settings.numbered_kinds:
            label = f"{method['kind'].capitalize()} {method['index']}"
            return f"## {label}: {title}" if title else f"## {label}"

        return f"## {title}" if title else ""
