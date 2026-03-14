from app.models.schemas import ChatCitation, ChatMessage, PromptContext, RetrievedChunk


SAFE_FALLBACK_TEXT = "I couldn't find that in the knowledge base."


class PromptBuilder:
    def build(
        self,
        user_message: str,
        chat_history: list[ChatMessage],
        retrieved_chunks: list[RetrievedChunk],
    ) -> PromptContext:
        system_prompt = (
            "You are a grounded RAG assistant. "
            "Answer only from the provided context. "
            "Do not invent services, pricing, experience, or facts not present in the context. "
            "If the context is insufficient, say you do not know."
        )

        citations = [
            ChatCitation(
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                url=chunk.url,
                source_type=chunk.source_type,
                snippet=chunk.content[:240],
                metadata=chunk.metadata,
            )
            for chunk in retrieved_chunks
        ]

        context_blocks = []
        for index, chunk in enumerate(retrieved_chunks, start=1):
            context_blocks.append(
                "\n".join(
                    [
                        f"[Source {index}]",
                        f"Title: {chunk.title}",
                        f"Source Type: {chunk.source_type}",
                        f"URL: {chunk.url or 'N/A'}",
                        f"Similarity: {chunk.similarity_score:.4f}",
                        f"Content: {chunk.content}",
                    ]
                )
            )

        user_prompt = "\n\n".join(
            [
                "Use the context below to answer the question.",
                "\n\n".join(context_blocks),
                f"Question: {user_message}",
                "If the answer is not in the context, respond that you do not know.",
            ]
        )

        messages = [ChatMessage(role="system", content=system_prompt)]
        messages.extend(chat_history)
        messages.append(ChatMessage(role="user", content=user_prompt))

        return PromptContext(
            system_prompt=system_prompt,
            messages=messages,
            citations=citations,
        )
