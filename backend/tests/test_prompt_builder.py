from app.models.schemas import ChatMessage, RetrievedChunk
from app.services.prompt_builder import PromptBuilder


def test_prompt_builder_includes_grounding_and_citations() -> None:
    builder = PromptBuilder()
    chunks = [
        RetrievedChunk(
            chunk_id="11111111-1111-1111-1111-111111111111",
            document_id="22222222-2222-2222-2222-222222222222",
            title="Service Catalog",
            url="https://example.com/catalog",
            source_type="md",
            content="We offer AI chatbot implementation for SME customers.",
            metadata={"section_title": "Services"},
            similarity_score=0.92,
        )
    ]

    prompt = builder.build(
        user_message="What services do we offer?",
        chat_history=[ChatMessage(role="user", content="Hi")],
        retrieved_chunks=chunks,
    )

    assert "Answer only from the provided context" in prompt.system_prompt
    assert "Question: What services do we offer?" in prompt.messages[-1].content
    assert prompt.citations[0].title == "Service Catalog"
