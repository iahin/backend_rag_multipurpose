from app.core.config import Settings
from app.models.schemas import NormalizedDocument
from app.services.chunking import ChunkingService


def test_chunking_splits_long_text() -> None:
    settings = Settings(
        chunk_size=40,
        chunk_overlap=5,
    )
    service = ChunkingService(settings)
    document = NormalizedDocument(
        title="Long Doc",
        source_type="text",
        content="A" * 100,
        metadata={},
    )

    chunks = service.build_chunks(document)

    assert len(chunks) >= 3
    assert chunks[0]["content"].startswith("Title: Long Doc")


def test_chunking_preserves_section_metadata() -> None:
    settings = Settings()
    service = ChunkingService(settings)
    document = NormalizedDocument(
        title="Policies",
        source_type="md",
        content="unused",
        metadata={"source_type": "md"},
        sections=[
            {"heading": "Billing", "content": "Invoices are sent monthly."},
            {"heading": "Support", "content": "Email support is available."},
        ],
    )

    chunks = service.build_chunks(document)

    assert len(chunks) == 2
    assert "Section: Billing" in chunks[0]["content"]
    assert chunks[0]["metadata"]["section_title"] == "Billing"
