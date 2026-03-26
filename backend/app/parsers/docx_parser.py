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
            looks_like_heading = self._looks_like_heading(text)

            if "heading" in style_name or looks_like_heading:
                if section_buffer:
                    sections.append(
                        {"heading": current_heading, "content": "\n".join(section_buffer).strip()}
                    )
                elif current_heading != "Introduction":
                    sections.append({"heading": current_heading, "content": current_heading})
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

    def _looks_like_heading(self, text: str) -> bool:
        normalized = text.strip()
        if not normalized or len(normalized) > 80:
            return False
        if normalized.endswith((".", ":", ";", ",")):
            return False

        words = normalized.split()
        if not words or len(words) > 8:
            return False

        if normalized.startswith("Step "):
            return True

        alpha_chars = [char for char in normalized if char.isalpha()]
        if alpha_chars and all(char.isupper() for char in alpha_chars):
            return True

        title_like_words = sum(1 for word in words if word[:1].isupper())
        if title_like_words >= max(1, len(words) - 1):
            return True

        return False
