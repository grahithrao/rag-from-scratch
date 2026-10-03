# RAG From Scratch

**Intelligent Document Question Answering System**

[![CI](https://github.com/organization/rag-from-scratch/actions/workflows/ci.yml/badge.svg)](https://github.com/organization/rag-from-scratch/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.118-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.50-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Persistent-orange.svg)](https://www.trychroma.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Upload your documents. Ask questions in plain English. Get answers that are
grounded in what the documents actually say — with the exact source passages
shown underneath every response.

This is a complete Retrieval-Augmented Generation pipeline built from the
components up: document parsing, chunking, local embeddings, a persistent vector
database, semantic retrieval, and a grounded LLM call — wired together behind a
FastAPI backend and a light, professional Streamlit interface.

The point of RAG is to stop a language model from making things up. This system
retrieves the relevant passages *first*, then asks the model to answer using only
those passages. When the documents do not contain the answer, it says so instead
of guessing.

---

## Features

- **Multi-format ingestion** — PDF, DOCX, TXT and Markdown, with page-level
  metadata preserved from parsing all the way through to the citation.
- **Local embeddings** — Sentence Transformers runs on your machine. No embedding
  API, no per-document cost, works offline after the first model download.
- **Persistent vector store** — ChromaDB on local disk. Restart the app and your
  indexed documents are still there.
- **Grounded generation** — a strict system prompt confines the model to the
  retrieved context and requires an explicit refusal when the answer is not there.
- **Real source citations** — every citation card is built from a chunk that was
  actually retrieved and actually sent to the model. Nothing is fabricated.
- **Content-hash deduplication** — uploading the same file twice is a no-op
  rather than a second copy in the index.
- **Full document management** — upload, list, re-index, delete one, clear all.
  Deleting a document removes its vectors from ChromaDB too.
- **Conversational follow-ups** — recent turns are carried forward for pronoun
  resolution, but history can never substitute for document evidence.
- **Retrieval you can inspect** — `POST /query` returns the retrieved chunks with
  no LLM involved, so you can see exactly what the model would have been given.
- **Refined Light SaaS Interface** — a Stripe/Notion-inspired interface
  with Inter typography, layered micro-shadows, pulse status badges, and
  interactive source citations locked to a light theme.
- **Enterprise Engineering Suite** — multi-stage Docker build, Docker Compose
  orchestration, automated Makefile developer workflows, PEP 621 `pyproject.toml`,
  and GitHub Actions CI.

---

## Architecture

```
                          User
                            │
                     Streamlit UI
                            │
                     FastAPI backend
                            │
                      RAG Pipeline
                            │
       ┌────────────────────┴────────────────────┐
       │                                         │
   INGESTION (once per document)          QUERY (per question)
       │                                         │
  Document Loader                          Question
  (PyMuPDF / python-docx)                       │
       │                                   Embed question
   Chunking                                     │
  (recursive, overlapping)               Semantic Retrieval
       │                                  (cosine, top-K)
   Embeddings                                   │
  (Sentence Transformers)                Relevant Context
       │                                         │
    ChromaDB  ─────────────────────────────►  Groq LLM
  (persistent vectors)                           │
                                          Grounded Answer
                                                 │
                                          Source Citations
```

The two halves meet at ChromaDB: ingestion writes vectors, querying reads them.
Retrieval and generation are deliberately separate modules, so either can be
swapped or tested on its own.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI, Uvicorn, Pydantic v2 |
| Frontend | Streamlit |
| Chunking | LangChain `RecursiveCharacterTextSplitter` |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`, 384-dim, local) |
| Vector database | ChromaDB (persistent, cosine distance) |
| LLM | Groq (`openai/gpt-oss-120b` by default) |
| PDF parsing | PyMuPDF |
| DOCX parsing | python-docx |
| Configuration | pydantic-settings + python-dotenv |
| Testing | pytest |

---

## How RAG Works

**1. Ingestion.** The uploaded file is validated (type, size, non-empty), given a
safe filename, and saved. PyMuPDF or python-docx extracts the text page by page.
Whitespace is normalised and words hyphenated across line breaks are rejoined.
The page number is captured here — it is the reason a citation can later say
"page 3".

**2. Chunking.** Page text is split into overlapping windows of ~1000 characters
with 150 characters of overlap, splitting on paragraph boundaries first and
falling back to sentences, then words. Overlap matters: without it, a sentence
that straddles a chunk boundary becomes unretrievable. Each chunk carries its
document ID, filename, page and chunk index.

**3. Embeddings.** Each chunk is encoded into a 384-dimensional unit vector by
`all-MiniLM-L6-v2`, running locally on CPU. Because the vectors are normalised,
cosine distance stays in a well-behaved `[0, 2]` range, which gives a stable
relevance threshold and a clean 0–100% match score for the UI.

**4. Vector storage.** Vectors and their metadata are written to a persistent
ChromaDB collection configured for cosine distance. Chunk IDs are deterministic
(`{document_id}:{index}`), so re-indexing replaces rather than duplicates.

**5. Retrieval.** The question is embedded with the *same* model. ChromaDB returns
the nearest chunks; the retriever over-fetches, drops anything beyond the distance
threshold, de-duplicates, and keeps the best Top-K. This step never calls the LLM.

**6. Generation.** The surviving chunks are formatted into a numbered context
block and sent to Groq alongside a system prompt that forbids outside knowledge
and mandates an explicit refusal when the context falls short. The answer is
returned with the exact chunks it was built from.

If retrieval finds nothing usable, the LLM is **not called at all** — the system
returns the refusal directly. A model that is never asked cannot hallucinate.

---

## Installation

```bash
# 1. Clone and enter the project
git clone <your-repo-url> rag-from-scratch
cd rag-from-scratch

# 2. Create and activate a virtual environment (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create your environment file
cp .env.example .env
```

Then open `.env` and paste in your Groq API key.

> The first run downloads the embedding model (~90 MB) from Hugging Face. That
> happens once; afterwards the app works without a network connection for
> everything except the Groq call.

---

## Environment Variables

Get a free API key at **[console.groq.com/keys](https://console.groq.com/keys)**.

> Groq retires models periodically. If generation fails with *"Groq does not
> serve the model…"*, check the live list at
> [console.groq.com/docs/models](https://console.groq.com/docs/models) and update
> `GROQ_MODEL`. Everything else in the pipeline is unaffected.

```bash
# .env  — required
GROQ_API_KEY=gsk_your_actual_key_here

# Optional — sensible defaults shown
GROQ_MODEL=openai/gpt-oss-120b
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=1024

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu

CHUNK_SIZE=1000
CHUNK_OVERLAP=150

TOP_K=5
MAX_DISTANCE=1.15
MAX_HISTORY_TURNS=4

MAX_UPLOAD_MB=25
API_PORT=8001
API_BASE_URL=http://127.0.0.1:8001
```

`.env` is listed in `.gitignore` and must never be committed. The key is read
server-side only — it is never sent to the browser.

---

## Running the Project

You can run the project using **Make** (recommended for local development), **Docker Compose** (recommended for containerized / isolated deployment), or manual commands.

### Method 1: Using Make (Recommended)

```bash
# Setup environment
cp .env.example .env    # Configure your GROQ_API_KEY
make install            # Sets up .venv and installs dependencies

# Run full stack (backend in background, Streamlit in foreground)
make run

# Or run in separate terminal tabs:
# Terminal 1: make run-backend
# Terminal 2: make run-frontend
```

### Method 2: Using Docker Compose

```bash
# Configure your environment
cp .env.example .env    # Configure your GROQ_API_KEY

# Start both services (backend on :8001, frontend on :8501)
make docker-up
# Or directly: docker compose up -d --build
```

- **Web Application UI**: [http://localhost:8501](http://localhost:8501)
- **FastAPI OpenAPI Interactive Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **System Health Endpoint**: [http://localhost:8001/health](http://localhost:8001/health)

To view logs or stop containers:
```bash
make docker-logs
make docker-down
```

### Method 3: Manual Startup

**Terminal 1 — Backend API:**
```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

**Terminal 2 — Frontend UI:**
```bash
source .venv/bin/activate
streamlit run frontend/streamlit_app.py
```

> **Port note:** the backend defaults to **8001**, not 8000, so it does not clash
> with other local services. If you change it, update `API_BASE_URL` too.
>
> **Run from the project root.** Streamlit resolves `.streamlit/config.toml`
> against the current working directory, and that file is what locks the light
> theme. Running the app from inside `frontend/` would silently lose the theme.

---

## Example Questions

Upload a document, then try:

- *What is this document about?*
- *Summarize the main points.*
- *What are the key conclusions?*
- *What were the evaluation results?*
- *What risks or limitations are mentioned?*
- *Explain the second recommendation in more detail.* ← follow-up, uses chat memory

To see the grounding actually work, ask something the document does not cover —
*"What is the capital of Peru?"* — and the system will tell you it could not find
that in your documents rather than answering from general knowledge.

A ready-made five-page `sample_report.pdf` ships with the project — upload that
to see the whole pipeline work immediately. To regenerate it:

```bash
python scripts/make_sample_pdf.py sample_report.pdf
# or: make sample-pdf
```

---

## Project Structure

```
rag-from-scratch/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated CI/CD pipeline (lint, test, Docker build)
├── .streamlit/
│   └── config.toml                # Light-theme lock (must stay at the root)
├── app/
│   ├── main.py                    # FastAPI app, timing middleware, /health, /config
│   ├── config.py                  # Centralised settings from environment
│   ├── api/
│   │   ├── documents.py           # Upload, list, delete, clear, re-index
│   │   └── chat.py                # /query (retrieval) and /chat (full RAG)
│   ├── rag/
│   │   ├── loader.py              # PDF/DOCX/TXT -> page text + metadata
│   │   ├── chunker.py             # Overlapping chunks, metadata preserved
│   │   ├── embeddings.py          # Local Sentence Transformers model
│   │   ├── vectorstore.py         # ChromaDB persistence and search
│   │   ├── retriever.py           # Semantic retrieval and ranking
│   │   ├── generator.py           # Groq call + the grounding prompt
│   │   ├── pipeline.py            # Retrieval -> generation orchestration
│   │   └── exceptions.py          # Domain errors carrying HTTP status codes
│   ├── services/
│   │   └── document_service.py    # Document lifecycle and the disk registry
│   └── models/
│       └── schemas.py             # Pydantic request/response models
├── frontend/
│   ├── streamlit_app.py           # Refined Light SaaS interface
│   ├── api_client.py              # Typed HTTP client for the backend
│   └── styles.py                  # Modern Stripe/Notion-inspired CSS design system
├── scripts/
│   ├── docker_entrypoint.sh       # Multi-mode container entrypoint
│   └── make_sample_pdf.py         # Generates a sample document for testing
├── tests/
│   ├── conftest.py                # Isolated storage + real PDF/DOCX fixtures
│   ├── test_loader.py             # Text extraction, all formats + failures
│   ├── test_chunker.py            # Chunking and metadata preservation
│   ├── test_retrieval.py          # Real embeddings, real ChromaDB, ranking
│   ├── test_pipeline.py           # Ingestion, management, grounding
│   ├── test_api.py                # Every endpoint, status codes, errors
│   └── test_frontend.py           # Streamlit renders without exceptions
├── data/
│   ├── uploads/                   # Stored source files
│   └── chroma/                    # Persistent vector database
├── Dockerfile                     # Multi-stage production container build
├── docker-compose.yml             # Orchestration for backend + frontend services
├── Makefile                       # Developer automation commands
├── pyproject.toml                 # PEP 621 packaging and tool configuration
├── .pre-commit-config.yaml        # Git commit quality hooks
├── sample_report.pdf              # Ready-made document to try the app with
├── .env.example                   # Annotated environment variable template
├── .gitignore                     # Git ignore rules
├── LICENSE                        # MIT License
├── pytest.ini                     # Pytest configuration
├── requirements.txt               # Pinned Python dependencies
└── README.md                      # Project documentation
```

---

## API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Component readiness — never fails |
| `GET` | `/config` | Non-secret configuration for the frontend |
| `POST` | `/documents/upload` | Upload, parse, chunk, embed and index a file |
| `GET` | `/documents` | List indexed documents with totals |
| `DELETE` | `/documents/{document_id}` | Delete one document and its vectors |
| `DELETE` | `/documents` | Clear everything |
| `POST` | `/documents/reindex/{document_id}` | Re-chunk and re-embed a stored file |
| `POST` | `/query` | Semantic retrieval only, no LLM |
| `POST` | `/chat` | Full RAG: retrieve, ground, generate, cite |

Interactive docs: **http://127.0.0.1:8001/docs**

---

## Testing

```bash
source .venv/bin/activate
pytest                       # whole suite
pytest -v                    # verbose
pytest tests/test_retrieval.py   # one module
```

The suite covers text extraction for all three formats (including corrupted and
empty files), chunk creation, metadata preservation end to end, vector storage
and deletion, semantic ranking quality, the full pipeline, every API endpoint,
and a headless render of the Streamlit UI — because a frontend error breaks the
app for the user without failing a single backend test.

Retrieval tests run against **real** embeddings and a **real** ChromaDB
collection in a temporary directory — the thing worth testing is whether semantic
search genuinely ranks relevant text above irrelevant text, which a mock cannot
tell you. Only the Groq call is mocked, so the suite is fast, free and offline.

---

## Troubleshooting

**`Cannot reach the backend at http://127.0.0.1:8001`**
The backend is not running, or it is on a different port. Start it with
`uvicorn app.main:app --port 8001` and confirm `API_BASE_URL` matches.

**`GROQ_API_KEY is not set`**
Copy `.env.example` to `.env`, paste a real key from console.groq.com, and
**restart the backend** — environment variables are read at startup.

**`Groq rejected the API key`**
The key is malformed or revoked. Generate a fresh one.

**`Groq does not serve the model '...'`**
Groq retires models periodically. Check the current list at
console.groq.com/docs/models and update `GROQ_MODEL`.

**`No text could be extracted`**
The PDF is a scan — an image with no text layer. This MVP does not perform OCR.
Run the file through an OCR tool first.

**`Address already in use`**
Something else holds the port. Use another one:
`uvicorn app.main:app --port 8002` (and update `API_BASE_URL`).

**First request is slow**
The embedding model loads on first use (~10–15 s) and downloads once (~90 MB).
Subsequent requests are fast.

**Answers ignore a document you just uploaded**
Check the sidebar shows it as *Indexed* with a chunk count above zero. If it says
Pending, use *Re-index*. Try raising Top-K if the document is large.

**Want to start completely fresh**
Stop the backend, then `rm -rf data/chroma data/uploads data/registry.json`.

---

## Future Improvements

- **OCR** for scanned PDFs, so image-only documents become searchable.
- **Hybrid retrieval** — combine dense vectors with BM25 keyword search, which
  materially helps for exact identifiers, product codes and names.
- **Cross-encoder reranking** of the top ~20 candidates before the final Top-K.
- **Streaming responses** so answers appear token by token.
- **Per-document access control** via metadata filtering.
- **Contradiction detection** to flag when retrieved chunks disagree rather than
  silently preferring the highest-ranked one.
- **Retrieval evaluation harness** — recall@k and faithfulness scoring on a
  labelled question set, to make prompt and chunking changes measurable.
- **Multi-user sessions** with persistent per-user conversation history.

---

## License

MIT — see below.

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
