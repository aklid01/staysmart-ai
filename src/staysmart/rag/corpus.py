from dataclasses import dataclass
from pathlib import Path

from staysmart.rag.errors import RagError

CATEGORY_BY_FILENAME = {
    "general.md": "general",
    "rooms.md": "rooms",
    "amenities.md": "amenities",
    "cancellation.md": "cancellation",
    "pet-policy.md": "pet_policy",
    "check-in-check-out.md": "check_in_check_out",
}

HOTEL_CATEGORIES = frozenset({"general", "rooms", "amenities", "cancellation", "pet_policy"})
KNOWN_CATEGORIES = frozenset(CATEGORY_BY_FILENAME.values())

ALLOWED_KEYS = frozenset({"doc_id", "category", "title", "hotel_id", "destination_id"})


@dataclass(frozen=True)
class KnowledgeDocument:
    doc_id: str
    category: str
    title: str
    hotel_id: str | None
    destination_id: str | None
    source_path: str
    body: str


def parse_frontmatter(text: str, source: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RagError(f"{source}: document must start with a frontmatter block (---)")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise RagError(f"{source}: frontmatter block is not closed") from exc

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped:
            continue
        key, separator, value = stripped.partition(":")
        if not separator:
            raise RagError(f"{source}: malformed frontmatter line {stripped!r}")
        fields[key.strip()] = value.strip()

    unknown = sorted(set(fields) - ALLOWED_KEYS)
    if unknown:
        raise RagError(f"{source}: unknown frontmatter keys {', '.join(unknown)}")
    for required in ("doc_id", "category", "title"):
        if not fields.get(required):
            raise RagError(f"{source}: frontmatter key {required!r} is required")
    if fields["category"] not in KNOWN_CATEGORIES:
        raise RagError(f"{source}: unknown category {fields['category']!r}")

    hotel_id = fields.get("hotel_id") or None
    destination_id = fields.get("destination_id") or None
    if fields["category"] in HOTEL_CATEGORIES:
        if not hotel_id:
            raise RagError(f"{source}: hotel documents require hotel_id")
        if destination_id:
            raise RagError(f"{source}: hotel documents must not carry destination_id")
    else:
        if not destination_id:
            raise RagError(f"{source}: destination documents require destination_id")
        if hotel_id:
            raise RagError(f"{source}: destination documents must not carry hotel_id")
    return fields


def load_corpus(corpus_path: Path) -> list[KnowledgeDocument]:
    if not corpus_path.is_dir():
        raise RagError(f"knowledge corpus path not found: {corpus_path}")
    files = sorted(p for p in corpus_path.rglob("*.md") if p.is_file())
    documents: list[KnowledgeDocument] = []
    seen: set[str] = set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(corpus_path).as_posix()
        fields = parse_frontmatter(text, relative)
        filename = path.name
        if filename not in CATEGORY_BY_FILENAME:
            raise RagError(f"{relative}: unrecognized knowledge document name")
        if fields["category"] != CATEGORY_BY_FILENAME[filename]:
            raise RagError(
                f"{relative}: category {fields['category']!r} does not match file name {filename!r}"
            )
        if fields["doc_id"] in seen:
            raise RagError(f"{relative}: duplicate doc_id {fields['doc_id']!r}")
        seen.add(fields["doc_id"])
        body = text.split("---", 2)[2].strip()
        documents.append(
            KnowledgeDocument(
                doc_id=fields["doc_id"],
                category=fields["category"],
                title=fields["title"],
                hotel_id=fields.get("hotel_id") or None,
                destination_id=fields.get("destination_id") or None,
                source_path=relative,
                body=body,
            )
        )
    return documents
