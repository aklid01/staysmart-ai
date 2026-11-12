from staysmart.rag.corpus import KnowledgeDocument
from staysmart.rag.models import KnowledgeChunk

MAX_CHUNK_CHARS = 600


def split_sections(body: str, overview_heading: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = overview_heading
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections.append((current_heading, "\n".join(current_lines).strip()))
    return [(heading, text) for heading, text in sections if text]


def split_paragraphs(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        if current and current_len + len(paragraph) + 2 > limit:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        if len(paragraph) + 2 > limit:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            chunks.append(paragraph)
            continue
        current.append(paragraph)
        current_len += len(paragraph) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_document(doc: KnowledgeDocument) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for heading, text in split_sections(doc.body, doc.title):
        for piece in split_paragraphs(text, MAX_CHUNK_CHARS):
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{doc.doc_id}:{len(chunks)}",
                    doc_id=doc.doc_id,
                    title=doc.title,
                    category=doc.category,
                    heading=heading,
                    source_path=doc.source_path,
                    text=piece,
                    hotel_id=doc.hotel_id,
                    destination_id=doc.destination_id,
                )
            )
    return chunks
