from abc import ABC, abstractmethod

from app.models.schemas import NormalizedDocument, ParsedFile


class FileParser(ABC):
    supported_types: tuple[str, ...]

    @abstractmethod
    async def parse(
        self,
        filename: str,
        content: bytes,
        mime_type: str | None,
        source_type_override: str | None = None,
        shared_metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> ParsedFile:
        raise NotImplementedError

    def build_document(
        self,
        *,
        title: str,
        source_type: str,
        content: str,
        metadata: dict,
        original_filename: str,
        mime_type: str | None,
        sections: list[dict] | None = None,
    ) -> NormalizedDocument:
        return NormalizedDocument(
            title=title,
            source_type=source_type,
            content=content,
            metadata=metadata,
            original_filename=original_filename,
            mime_type=mime_type,
            sections=sections or [],
        )
