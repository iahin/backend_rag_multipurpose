from app.models.schemas import ParsedFile
from app.parsers.base import FileParser


class MarkdownParser(FileParser):
    supported_types = ("md",)

    async def parse(
        self,
        filename: str,
        content: bytes,
        mime_type: str | None,
        source_type_override: str | None = None,
        shared_metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> ParsedFile:
        text = content.decode("utf-8-sig").strip()
        if not text:
            raise ValueError("empty file")

        sections: list[dict] = []
        current_heading = "Introduction"
        buffer: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                if buffer:
                    sections.append(
                        {"heading": current_heading, "content": "\n".join(buffer).strip()}
                    )
                current_heading = stripped.lstrip("#").strip() or "Untitled Section"
                buffer = []
                continue
            buffer.append(line)

        if buffer:
            sections.append({"heading": current_heading, "content": "\n".join(buffer).strip()})

        metadata = dict(shared_metadata or {})
        metadata["tags"] = tags or []

        document = self.build_document(
            title=filename.rsplit(".", 1)[0],
            source_type=source_type_override or "md",
            content=text,
            metadata=metadata,
            original_filename=filename,
            mime_type=mime_type,
            sections=sections,
        )

        return ParsedFile(filename=filename, detected_type="md", documents=[document])
