from io import BytesIO

from docx import Document

from app.models.schemas import ParsedFile
from app.parsers.base import FileParser


class DocxParser(FileParser):
    supported_types = ("docx",)

    async def parse(
        self,
        filename: str,
        content: bytes,
        mime_type: str | None,
        source_type_override: str | None = None,
        shared_metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> ParsedFile:
        doc = Document(BytesIO(content))
        sections: list[dict] = []
        paragraphs: list[str] = []
        current_heading = "Introduction"
        section_buffer: list[str] = []

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue

            paragraphs.append(text)
            style_name = paragraph.style.name.lower() if paragraph.style and paragraph.style.name else ""

            if "heading" in style_name:
                if section_buffer:
                    sections.append(
                        {"heading": current_heading, "content": "\n".join(section_buffer).strip()}
                    )
                current_heading = text
                section_buffer = []
            else:
                section_buffer.append(text)

        if section_buffer:
            sections.append({"heading": current_heading, "content": "\n".join(section_buffer).strip()})

        combined_text = "\n\n".join(paragraphs).strip()
        if not combined_text:
            raise ValueError("empty file")

        metadata = dict(shared_metadata or {})
        metadata["tags"] = tags or []

        document = self.build_document(
            title=filename.rsplit(".", 1)[0],
            source_type=source_type_override or "docx",
            content=combined_text,
            metadata=metadata,
            original_filename=filename,
            mime_type=mime_type,
            sections=sections,
        )

        return ParsedFile(filename=filename, detected_type="docx", documents=[document])
