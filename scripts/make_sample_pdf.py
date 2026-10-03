"""Generate a realistic multi-page sample PDF for manual testing.

Usage:  python scripts/make_sample_pdf.py [output.pdf]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

PAGES: list[tuple[str, str]] = [
    (
        "1. Executive Summary",
        "Northwind Analytics deployed a retrieval-augmented question answering "
        "system across its internal documentation in the third quarter. The "
        "programme covered 14,200 documents drawn from engineering runbooks, "
        "customer support transcripts and the compliance handbook.\n\n"
        "Average time to locate an authoritative answer fell from 8.4 minutes to "
        "41 seconds. Support ticket deflection improved by 23 percent. The total "
        "infrastructure cost was 1,180 US dollars per month, of which 62 percent "
        "was inference and 38 percent was vector storage.\n\n"
        "The board approved a phase two rollout to the field sales organisation, "
        "scheduled to begin in January.",
    ),
    (
        "2. System Architecture",
        "Documents enter the pipeline through a watched object store bucket. Each "
        "file is parsed, normalised and split into overlapping windows of roughly "
        "1,000 characters with 150 characters of overlap. Overlap matters because "
        "a sentence split across a boundary otherwise becomes unretrievable.\n\n"
        "Chunks are embedded with the all-MiniLM-L6-v2 sentence transformer, which "
        "produces 384-dimensional vectors. Vectors are written to a ChromaDB "
        "collection configured for cosine distance.\n\n"
        "At query time the user question is embedded with the same model. The five "
        "nearest chunks are retrieved, filtered by a distance threshold, and "
        "assembled into a numbered context block that is passed to the language "
        "model together with a grounding instruction.",
    ),
    (
        "3. Evaluation Results",
        "The team evaluated the system against a held-out set of 480 questions "
        "written by domain experts. Answer accuracy, judged by human raters, "
        "reached 91.2 percent. Retrieval recall at five was 88.7 percent.\n\n"
        "Hallucination rate, defined as any factual claim not supported by the "
        "retrieved context, was measured at 2.1 percent, down from 19.6 percent "
        "for the same model prompted without retrieval. This single figure was the "
        "strongest argument for the programme's continued funding.\n\n"
        "Median end-to-end latency was 1.9 seconds at the ninety-fifth percentile, "
        "well inside the three-second target agreed with the support organisation.",
    ),
    (
        "4. Risks and Limitations",
        "Scanned documents without a text layer are not indexed. An optical "
        "character recognition stage is planned but not yet funded.\n\n"
        "The system does not currently reconcile contradictory sources. When two "
        "documents disagree, the answer reflects whichever chunk ranked higher, "
        "and the contradiction is not surfaced to the reader.\n\n"
        "Access control is enforced at the collection level rather than the "
        "document level. Until per-document filtering ships, the compliance "
        "handbook is indexed in a separate collection restricted to the legal team.",
    ),
    (
        "5. Recommendations",
        "First, fund the optical character recognition stage. Roughly 6 percent of "
        "the corpus is currently invisible to search.\n\n"
        "Second, add a contradiction detector that flags when retrieved chunks "
        "disagree, rather than silently preferring the top-ranked one.\n\n"
        "Third, migrate access control to per-document metadata filtering so that "
        "a single collection can serve every team.\n\n"
        "Fourth, re-evaluate the embedding model each quarter. The field moves "
        "quickly and a better model is the cheapest available accuracy gain.",
    ),
]


def build(output: Path) -> Path:
    """Write the sample report to ``output`` and return the path."""
    document = pymupdf.open()
    for index, (heading, body) in enumerate(PAGES, start=1):
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(60, 60, 540, 110),
            "Northwind Analytics - RAG Deployment Report",
            fontsize=9,
            color=(0.4, 0.4, 0.45),
        )
        page.insert_textbox(
            pymupdf.Rect(60, 95, 540, 140), heading, fontsize=16, fontname="hebo"
        )
        page.insert_textbox(
            pymupdf.Rect(60, 150, 540, 740), body, fontsize=11, lineheight=1.45
        )
        page.insert_textbox(
            pymupdf.Rect(60, 750, 540, 780),
            f"Page {index} of {len(PAGES)}",
            fontsize=8,
            color=(0.55, 0.55, 0.6),
        )
    document.save(output)
    document.close()
    return output


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "sample_report.pdf")
    print(f"Wrote {build(target)}")
