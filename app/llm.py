import anthropic

from app.config import settings

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def answer_with_context(question: str, chunks: list[dict]) -> str:
    if not chunks:
        return (
            "Não encontrei documentos indexados para responder sua pergunta. "
            "Por favor, envie um documento (PDF, Word, imagem ou .txt) primeiro."
        )

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"[Fonte: {chunk['source']} | Trecho {i}]\n{chunk['text']}")

    context = "\n\n---\n\n".join(context_parts)

    system = (
        "Você é um assistente especializado em responder perguntas com base em documentos fornecidos. "
        "Responda APENAS com informações presentes nos trechos abaixo. "
        "Se a informação não estiver nos trechos, diga claramente que não encontrou nos documentos. "
        "Seja claro, objetivo e cite a fonte quando possível. Responda sempre em português."
    )

    prompt = f"""Com base nos seguintes trechos dos documentos:

{context}

Pergunta: {question}

Resposta:"""

    client = _get_client()
    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
