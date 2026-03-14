from app.models.schemas import ParsedFile
from app.parsers.base import FileParser


class TextParser(FileParser):
    supported_types = ("txt",)

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

        metadata = dict(shared_metadata or {})
        metadata["tags"] = tags or []

        document = self.build_document(
            title=filename.rsplit(".", 1)[0],
            source_type=source_type_override or "txt",
            content=text,
            metadata=metadata,
            original_filename=filename,
            mime_type=mime_type,
        )

        return ParsedFile(filename=filename, detected_type="txt", documents=[document])
