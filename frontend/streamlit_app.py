"""RAG From Scratch — Streamlit frontend.

A light, single-page chat interface over the FastAPI backend. All retrieval,
embedding and LLM work happens server-side; this module only renders state and
forwards user actions.

Run with:  streamlit run frontend/streamlit_app.py
"""

from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_client import APIError, RAGClient  # noqa: E402
from styles import CSS, logo_mark, search_mark  # noqa: E402

SUPPORTED_TYPES = ["pdf", "docx", "txt", "md"]
# Material Symbols rather than emoji: one consistent icon set, no colour clash.
USER_ICON = ":material/person:"
ASSISTANT_ICON = ":material/auto_awesome:"
EXAMPLE_QUESTIONS = [
    "What is this document about?",
    "Summarize the main points.",
    "What are the key conclusions?",
]
PREVIEW_CHARS = 260

st.set_page_config(
    page_title="RAG From Scratch",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------- state
def init_state() -> None:
    """Seed every session key exactly once."""
    defaults: dict[str, Any] = {
        "messages": [],       # [{role, content, sources, meta}]
        "documents": [],
        "totals": {"documents": 0, "chunks": 0},
        "health": None,
        "config": None,
        "pending_question": None,
        "flash": None,        # (level, message)
        "uploader_key": 0,    # Bumped to reset the file uploader widget.
        "top_k": 5,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


@st.cache_resource
def get_client() -> RAGClient:
    """One HTTP client for the session."""
    return RAGClient()


def flash(level: str, message: str) -> None:
    """Queue a banner to render on the next run."""
    st.session_state.flash = (level, message)


def refresh_backend_state() -> None:
    """Pull health and the document list from the backend."""
    client = get_client()
    try:
        st.session_state.health = client.health()
    except APIError as exc:
        st.session_state.health = {"status": "unreachable", "detail": exc.message}
        return
    try:
        payload = client.list_documents()
        st.session_state.documents = payload.get("documents", [])
        st.session_state.totals = {
            "documents": payload.get("total_documents", 0),
            "chunks": payload.get("total_chunks", 0),
        }
    except APIError as exc:
        flash("error", exc.message)
    if st.session_state.config is None:
        try:
            st.session_state.config = client.config()
            st.session_state.top_k = st.session_state.config.get("top_k", 5)
        except APIError:
            pass


# ------------------------------------------------------------------ rendering
def esc(text: Any) -> str:
    """HTML-escape untrusted text before it goes into a markup string."""
    return html.escape(str(text), quote=True)


def render_header() -> None:
    """Product header with a live system-status pill."""
    health = st.session_state.health or {}
    status = health.get("status")

    if status == "ok":
        tone, label = "ok", "System ready"
    elif status == "degraded":
        tone, label = "warn", "Limited mode"
    elif status == "unreachable":
        tone, label = "bad", "Backend offline"
    else:
        tone, label = "warn", "Connecting"

    model = (health.get("llm_model") or "").split("/")[-1]
    model_pill = (
        f'<span class="pill"><b>{esc(model)}</b></span>' if model and status == "ok" else ""
    )

    st.markdown(
        f"""
        <div class="hd">
          <div class="hd__l">
            <div class="hd__mark">{logo_mark()}</div>
            <div>
              <h1 class="hd__t">RAG From Scratch</h1>
              <p class="hd__s">Ask questions about your documents using
              Retrieval-Augmented Generation.</p>
            </div>
          </div>
          <div style="display:flex;gap:.45rem;align-items:center">
            {model_pill}
            <span class="pill pill--{tone}"><span class="dot"></span>{esc(label)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    """Shown until the first question is asked."""
    st.markdown(
        f"""
        <div class="zero">
          <div class="zero__mark">{search_mark()}</div>
          <h2 class="zero__t">Your documents, now searchable.</h2>
          <p class="zero__s">Upload a document and ask a question to get started.
          Every answer is grounded in the text that was actually retrieved, with its
          sources shown underneath.</p>
          <div class="zero__features">
            <div class="feat-card">
              <span class="feat-card__icon">🛡️</span>
              <span class="feat-card__title">Strict Grounding</span>
              <span class="feat-card__desc">Refuses to hallucinate when facts are absent</span>
            </div>
            <div class="feat-card">
              <span class="feat-card__icon">📑</span>
              <span class="feat-card__title">Exact Citations</span>
              <span class="feat-card__desc">Page-level source tracking on every answer</span>
            </div>
            <div class="feat-card">
              <span class="feat-card__icon">⚡</span>
              <span class="feat-card__title">Local Embeddings</span>
              <span class="feat-card__desc">Private, zero-cost vectors on ChromaDB</span>
            </div>
          </div>
          <p class="zero__lbl">Try asking</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    has_documents = bool(st.session_state.documents)
    st.markdown('<div class="chips">', unsafe_allow_html=True)
    columns = st.columns(len(EXAMPLE_QUESTIONS), gap="small")
    for column, question in zip(columns, EXAMPLE_QUESTIONS):
        with column:
            if st.button(
                question,
                key=f"example_{question}",
                disabled=not has_documents,
                use_container_width=True,
            ):
                ask(question)
    st.markdown("</div>", unsafe_allow_html=True)

    if not has_documents:
        st.caption("Upload a document in the sidebar to enable these.")


def render_sources(sources: list[dict[str, Any]]) -> None:
    """Citation cards — one per chunk that was actually sent to the model."""
    if not sources:
        return
    st.markdown(
        f'<p class="src-h">Sources · {len(sources)}</p>', unsafe_allow_html=True
    )
    for position, source in enumerate(sources, start=1):
        text = " ".join(source.get("text", "").split())
        preview = text[:PREVIEW_CHARS] + ("…" if len(text) > PREVIEW_CHARS else "")
        page = source.get("page")
        page_ref = f'<span class="src__p">p.{esc(page)}</span>' if page else ""
        score = float(source.get("score", 0.0))
        st.markdown(
            f"""
            <div class="src">
              <div class="src__t">
                <span class="src__n">{position}</span>
                <span class="src__f">{esc(source.get("filename", "unknown"))}</span>
                <span class="src__r">{page_ref}
                  <span class="src__m">{score:.0%}</span>
                </span>
              </div>
              <p class="src__x">{esc(preview)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_message(message: dict[str, Any]) -> None:
    """Render one turn of the conversation."""
    if message["role"] == "user":
        with st.chat_message("user", avatar=USER_ICON):
            st.markdown(
                f'<p class="ask">{esc(message["content"])}</p>', unsafe_allow_html=True
            )
        return

    with st.chat_message("assistant", avatar=ASSISTANT_ICON):
        if message.get("error"):
            st.error(message["content"])
            return

        # Streamlit renders the markdown; the wrapper scopes our typography to it.
        wrapper = "say" if message.get("grounded", True) else "nores"
        st.markdown(f'<div class="{wrapper}">', unsafe_allow_html=True)
        st.markdown(message["content"])
        st.markdown("</div>", unsafe_allow_html=True)

        meta = message.get("meta") or {}
        if meta:
            st.markdown(
                f"""<div class="meta">
                  <span><b>{esc((meta.get("model") or "").split("/")[-1])}</b></span>
                  <span>retrieval <b>{meta.get("retrieval_ms", 0):.0f} ms</b></span>
                  <span>generation <b>{meta.get("generation_ms", 0):.0f} ms</b></span>
                </div>""",
                unsafe_allow_html=True,
            )

        if message.get("sources"):
            render_sources(message["sources"])


# -------------------------------------------------------------------- actions
def ask(question: str) -> None:
    """Queue a question and rerun so the user turn paints immediately."""
    st.session_state.pending_question = question
    st.rerun()


def answer_pending_question() -> None:
    """Send the queued question through the backend RAG pipeline."""
    question = st.session_state.pending_question
    st.session_state.pending_question = None

    st.session_state.messages.append({"role": "user", "content": question})
    render_message(st.session_state.messages[-1])

    # Only completed turns become history; the current question is sent separately.
    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages[:-1]
        if not message.get("error")
    ]

    with st.chat_message("assistant", avatar=ASSISTANT_ICON):
        with st.spinner("Searching your documents…"):
            try:
                response = get_client().chat(
                    question=question,
                    history=history,
                    top_k=st.session_state.top_k,
                )
            except APIError as exc:
                st.session_state.messages.append(
                    {"role": "assistant", "content": exc.message, "error": True}
                )
                st.rerun()
                return

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response["answer"],
            "sources": response.get("sources", []),
            "grounded": response.get("grounded", True),
            "meta": {
                "model": response.get("model", ""),
                "retrieval_ms": response.get("retrieval_ms", 0),
                "generation_ms": response.get("generation_ms", 0),
            },
        }
    )
    st.rerun()


def handle_uploads(files: list[Any]) -> None:
    """Upload each new file to the backend and report the outcome."""
    client = get_client()
    indexed, skipped, failed = [], [], []

    progress = st.sidebar.progress(0.0, text="Indexing…")
    for position, file in enumerate(files, start=1):
        progress.progress(
            (position - 1) / len(files), text=f"Indexing {file.name}…"
        )
        try:
            result = client.upload_document(file.name, file.getvalue(), file.type)
        except APIError as exc:
            failed.append(f"{file.name}: {exc.message}")
            continue
        if result.get("already_indexed"):
            skipped.append(file.name)
        else:
            indexed.append(f"{file.name} ({result['document']['num_chunks']} chunks)")
    progress.empty()

    parts: list[str] = []
    if indexed:
        parts.append("Indexed " + ", ".join(indexed) + ".")
    if skipped:
        parts.append("Already indexed: " + ", ".join(skipped) + ".")
    if failed:
        flash("error", " ".join(failed))
    elif parts:
        flash("success", " ".join(parts))

    st.session_state.uploader_key += 1  # Reset the widget so re-upload works.
    st.rerun()


# -------------------------------------------------------------------- sidebar
def _plural(count: int, noun: str) -> str:
    """Naive pluralisation - every noun this UI counts is regular."""
    return noun if count == 1 else f"{noun}s"


def _format_size(num_bytes: int) -> str:
    """Human-readable file size that never rounds a real file down to '0 KB'."""
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes} B"


def render_document_card(document: dict[str, Any]) -> None:
    """One dense document row plus its re-index / delete actions."""
    file_type = document.get("file_type", "txt")
    status = document.get("status", "pending")
    tone = {"indexed": "ok", "failed": "bad"}.get(status, "warn")

    pages = document.get("num_pages", 0)
    parts = [
f"{document.get('num_chunks', 0)} {_plural(document.get('num_chunks', 0), 'chunk')}",
f"{pages} {_plural(pages, 'page')}",
        _format_size(document.get("size_bytes", 0)),
    ]
    meta = "".join(f"<span>{esc(part)}</span>" for part in parts)
    error = (
        f'<p class="doc__err">{esc(document["error"])}</p>' if document.get("error") else ""
    )

    st.markdown(
        f"""
        <div class="doc">
          <div class="doc__t">
            <span class="doc__ext doc__ext--{esc(file_type)}">{esc(file_type)}</span>
            <span class="doc__n" title="{esc(document.get("filename", ""))}">{esc(document.get("filename", "unknown"))}</span>
            <span class="doc__st" title="{esc(status)}"><span class="dot pill--{tone}"
              style="background:var(--{tone})"></span></span>
          </div>
          <div class="doc__m">{meta}</div>
          {error}
        </div>
        """,
        unsafe_allow_html=True,
    )

    document_id = document["document_id"]
    st.markdown('<div class="rowact">', unsafe_allow_html=True)
    _, reindex_col, delete_col = st.columns([4, 1, 1], gap="small")
    with reindex_col:
        if st.button(
            "", icon=":material/refresh:", key=f"reindex_{document_id}",
            help="Re-chunk and re-embed this document",
        ):
            with st.spinner("Re-indexing…"):
                try:
                    result = get_client().reindex_document(document_id)
                    flash(
                        "success",
                        f"Re-indexed '{result['filename']}' into "
                        f"{result['num_chunks']} chunks.",
                    )
                except APIError as exc:
                    flash("error", exc.message)
            st.rerun()
    with delete_col:
        if st.button(
            "", icon=":material/delete:", key=f"delete_{document_id}",
            help="Delete this document and its vectors",
        ):
            try:
                result = get_client().delete_document(document_id)
                flash("success", result["message"])
            except APIError as exc:
                flash("error", exc.message)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar() -> None:
    """Upload, the indexed corpus, retrieval settings and system details."""
    with st.sidebar:
        st.markdown('<p class="sec">Documents</p>', unsafe_allow_html=True)

        files = st.file_uploader(
            "Upload Documents",
            type=SUPPORTED_TYPES,
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}",
            label_visibility="collapsed",
        )
        if files:
            st.markdown('<div style="height:.45rem"></div>', unsafe_allow_html=True)
            if st.button(
                f"Index {len(files)} file{'s' if len(files) != 1 else ''}",
                type="primary",
                icon=":material/bolt:",
                use_container_width=True,
            ):
                handle_uploads(files)

        documents = st.session_state.documents
        totals = st.session_state.totals

        st.markdown(
            f'<p class="sec">Indexed<b>{len(documents)}</b></p>', unsafe_allow_html=True
        )
        if not documents:
            st.markdown(
                '<div class="none">Nothing indexed yet.<br/>'
                "Upload a document to start asking questions.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""<div class="tally">
                  <span><b>{totals["documents"]}</b> {_plural(totals["documents"], "document")}</span><i></i>
                  <span><b>{totals["chunks"]}</b> {_plural(totals["chunks"], "chunk")}</span>
                </div>
                <div style="height:.55rem"></div>""",
                unsafe_allow_html=True,
            )
            for document in documents:
                render_document_card(document)

            st.markdown('<div style="height:.35rem"></div>', unsafe_allow_html=True)
            if st.button(
                "Clear all documents",
                icon=":material/delete_sweep:",
                use_container_width=True,
            ):
                try:
                    result = get_client().clear_documents()
                    st.session_state.messages = []
                    flash("success", result["message"])
                except APIError as exc:
                    flash("error", exc.message)
                st.rerun()

        # ---------------------------------------------------------- retrieval
        st.markdown('<p class="sec">Retrieval</p>', unsafe_allow_html=True)
        st.session_state.top_k = st.slider(
            "Chunks per question (Top-K)",
            min_value=1,
            max_value=15,
            value=st.session_state.top_k,
            help="How many document chunks are retrieved and sent to the model.",
        )
        if st.session_state.messages and st.button(
            "Clear conversation",
            icon=":material/restart_alt:",
            use_container_width=True,
        ):
            st.session_state.messages = []
            st.rerun()

        # ------------------------------------------------------------- system
        config = st.session_state.config or {}
        health = st.session_state.health or {}
        st.markdown('<p class="sec">System</p>', unsafe_allow_html=True)
        with st.expander("Pipeline", expanded=False):
            rows = [
                ("Model", config.get("llm_model", "—")),
                ("Embeddings", (config.get("embedding_model") or "—").split("/")[-1]),
                ("Vector store", "ChromaDB"),
                ("Chunk size", f"{config.get('chunk_size', '—')}"),
                ("Overlap", f"{config.get('chunk_overlap', '—')}"),
            ]
            st.markdown(
                "".join(
                    f'<div class="kv"><span class="kv__k">{esc(k)}</span>'
                    f'<span class="kv__v" title="{esc(v)}">{esc(v)}</span></div>'
                    for k, v in rows
                ),
                unsafe_allow_html=True,
            )
            if health.get("detail"):
                st.caption(health["detail"])


# ----------------------------------------------------------------------- main
def main() -> None:
    init_state()
    st.markdown(CSS, unsafe_allow_html=True)
    refresh_backend_state()

    render_header()
    render_sidebar()

    if st.session_state.flash:
        level, message = st.session_state.flash
        st.session_state.flash = None
        {"success": st.success, "error": st.error, "warning": st.warning}.get(
            level, st.info
        )(message)

    health = st.session_state.health or {}
    if health.get("status") == "unreachable":
        st.error(health.get("detail", "The backend is not reachable."))
        st.code("uvicorn app.main:app --host 127.0.0.1 --port 8001", language="bash")
        return
    if not health.get("llm_configured", True):
        st.warning(
            "**GROQ_API_KEY is not configured.** Search works, but answers cannot be "
            "generated. Add your key from console.groq.com to `.env` and restart the "
            "backend."
        )

    for message in st.session_state.messages:
        render_message(message)

    if not st.session_state.messages and not st.session_state.pending_question:
        render_empty_state()

    if st.session_state.pending_question:
        answer_pending_question()

    has_documents = bool(st.session_state.documents)
    question = st.chat_input(
        "Ask something about your documents…"
        if has_documents
        else "Upload a document to start asking questions…",
        disabled=not has_documents,
    )
    if question:
        ask(question)


if __name__ == "__main__":
    main()
