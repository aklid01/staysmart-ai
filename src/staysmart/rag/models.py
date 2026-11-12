from pydantic import Field

from staysmart.domain.models import StrictModel


class KnowledgeChunk(StrictModel):
    chunk_id: str
    doc_id: str
    title: str
    category: str
    heading: str
    source_path: str
    text: str
    hotel_id: str | None = None
    destination_id: str | None = None

    def embedded_text(self) -> str:
        return f"{self.title} - {self.heading}\n{self.text}"

    def formatted_block(self) -> str:
        return f"{self.title} - {self.heading}: {self.text}"


class RetrievedChunk(StrictModel):
    chunk: KnowledgeChunk
    score: float

    def formatted_block(self) -> str:
        return self.chunk.formatted_block()


class ContextSource(StrictModel):
    doc_id: str
    title: str
    category: str
    chunk_count: int = Field(ge=1)
    hotel_id: str | None = None
    destination_id: str | None = None


class ContextBundle(StrictModel):
    query: str
    chunks: list[RetrievedChunk]
    sources: list[ContextSource]
    formatted_context: str
