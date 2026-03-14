import csv
from io import StringIO

from app.models.schemas import NormalizedDocument, ParsedFile
from app.parsers.base import FileParser


class CsvParser(FileParser):
    supported_types = ("csv",)

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

        reader = csv.DictReader(StringIO(text))
        if not reader.fieldnames:
            raise ValueError("csv file is missing headers")

        base_metadata = dict(shared_metadata or {})
        base_metadata["tags"] = tags or []
        documents: list[NormalizedDocument] = []

        for row_index, row in enumerate(reader, start=2):
            if not any(value and str(value).strip() for value in row.values()):
                continue

            row_lines = [f"{column}: {row.get(column, '')}" for column in reader.fieldnames]
            row_text = "\n".join([f"File: {filename}", f"Row: {row_index}", *row_lines]).strip()

            metadata = dict(base_metadata)
            metadata.update(
                {
                    "row_start": row_index,
                    "row_end": row_index,
                    "column_headers": reader.fieldnames,
                }
            )

            documents.append(
                self.build_document(
                    title=f"{filename} row {row_index}",
                    source_type=source_type_override or "csv",
                    content=row_text,
                    metadata=metadata,
                    original_filename=filename,
                    mime_type=mime_type,
                )
            )

        if not documents:
            raise ValueError("csv file has no readable rows")

        return ParsedFile(filename=filename, detected_type="csv", documents=documents)
