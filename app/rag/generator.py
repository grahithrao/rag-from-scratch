"""Grounded answer generation with Groq.

The system prompt is the anti-hallucination contract: the model answers only
from the retrieved context and says so plainly when the context does not cover
the question. Conversation history is supplied for pronoun resolution and
follow-ups, never as a substitute source of facts.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from app.config import settings
from app.models.schemas import ChatMessage, SourceChunk
from app.rag.exceptions import LLMConfigurationError, LLMError
from app.rag.retriever import format_context

logger = logging.getLogger(__name__)

NO_ANSWER_MESSAGE = "I couldn't find this information in the uploaded documents."

SYSTEM_PROMPT = """You are a precise document analyst. You answer questions \
strictly from the excerpts supplied to you, which were retrieved from documents \
the user uploaded.

RULES — follow all of them:
1. Base every factual statement on the CONTEXT below. Never use outside knowledge \
and never guess.
2. If the context does not contain the answer, reply with exactly: \
"{no_answer}" — optionally followed by one sentence naming what the documents do \
cover instead. Do not attempt a partial answer built on assumptions.
3. If the context answers the question only partially, give what is supported and \
state clearly which part is not covered by the documents.
4. Cite the sources you used inline as [Source 1], [Source 2], and so on, matching \
the numbering in the context.
5. Prior conversation turns are for understanding what the user is referring to. \
They are never evidence — facts must come from the context.
6. Write for a reader in a hurry: lead with the answer, then support it. Use \
markdown — short paragraphs, bullet points for lists, numbered lists for \
sequences, code blocks for code or structured data.
7. Do not mention retrieval, embeddings, or that you were "given context". Just \
answer.""".format(no_answer=NO_ANSWER_MESSAGE)

USER_TEMPLATE = """CONTEXT
=======
{context}

QUESTION
========
{question}

Answer the question using only the context above, citing sources as [Source N]."""

_client = None
_client_key: str | None = None
_lock = threading.Lock()


@dataclass(slots=True)
class GenerationResult:
    """A generated answer plus the metadata the UI reports."""

    answer: str
    model: str
    elapsed_ms: float
    grounded: bool


def _get_client():
    """Return a cached Groq client, rebuilding it if the key changed."""
    global _client, _client_key

    if not settings.has_groq_key:
        raise LLMConfigurationError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://console.groq.com/keys, then restart the backend."
        )

    key = settings.groq_api_key.strip()
    if _client is not None and _client_key == key:
        return _client

    with _lock:
        from groq import Groq

        try:
            _client = Groq(api_key=key, timeout=settings.llm_timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            raise LLMConfigurationError(f"Could not initialise the Groq client: {exc}") from exc
        _client_key = key
        return _client


def build_messages(
    question: str,
    sources: list[SourceChunk],
    history: list[ChatMessage] | None = None,
) -> list[dict[str, str]]:
    """Assemble the system + history + context/question message list."""
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history and settings.max_history_turns > 0:
        # Keep only the most recent turns so old context cannot crowd out the
        # retrieved evidence for the current question.
        recent = history[-(settings.max_history_turns * 2) :]
        for message in recent:
            content = message.content.strip()
            if content:
                messages.append({"role": message.role, "content": content})

    messages.append(
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                context=format_context(sources), question=question
            ),
        }
    )
    return messages


def _translate_groq_error(exc: Exception) -> Exception:
    """Turn a Groq SDK exception into an actionable domain error."""
    from groq import (
        APIConnectionError,
        APIStatusError,
        AuthenticationError,
        RateLimitError,
    )

    if isinstance(exc, AuthenticationError):
        return LLMConfigurationError(
            "Groq rejected the API key. Check GROQ_API_KEY in your .env file."
        )
    if isinstance(exc, RateLimitError):
        return LLMError(
            "Groq rate limit reached. Wait a few seconds and try again."
        )
    if isinstance(exc, APIConnectionError):
        return LLMError(
            "Could not reach Groq. Check your network connection and try again."
        )
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", "unknown")
        if status == 404:
            return LLMConfigurationError(
                f"Groq does not serve the model '{settings.groq_model}'. Update "
                f"GROQ_MODEL in your .env to a currently available model."
            )
        return LLMError(f"Groq returned an error (HTTP {status}): {exc}")
    return LLMError(f"Answer generation failed: {exc}")


def generate_answer(
    question: str,
    sources: list[SourceChunk],
    history: list[ChatMessage] | None = None,
    model: str | None = None,
) -> GenerationResult:
    """Generate an answer grounded in ``sources``.

    Short-circuits without calling the LLM when retrieval found nothing, which
    keeps the "no answer" path fast and guarantees it cannot hallucinate.

    Raises:
        LLMConfigurationError: missing or rejected API key, unknown model.
        LLMError: transport, rate-limit or upstream failure.
    """
    started = time.perf_counter()
    model_name = model or settings.groq_model

    if not sources:
        return GenerationResult(
            answer=(
                f"{NO_ANSWER_MESSAGE}\n\nTry rephrasing your question, or upload a "
                f"document that covers this topic."
            ),
            model=model_name,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            grounded=False,
        )

    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=build_messages(question, sources, history),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 - translated into domain errors below
        raise _translate_groq_error(exc) from exc

    answer = (completion.choices[0].message.content or "").strip()
    if not answer:
        answer = NO_ANSWER_MESSAGE

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("Generated %d chars with %s in %.0f ms", len(answer), model_name, elapsed_ms)
    return GenerationResult(
        answer=answer,
        model=model_name,
        elapsed_ms=round(elapsed_ms, 2),
        grounded=True,
    )


def reset_client() -> None:
    """Drop the cached client so the next call picks up a new key."""
    global _client, _client_key
    with _lock:
        _client = None
        _client_key = None
