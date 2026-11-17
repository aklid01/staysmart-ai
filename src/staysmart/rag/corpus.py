import hashlib
from dataclasses import dataclass
from pathlib import Path

from staysmart.rag.errors import RagError
from staysmart.rag.models import Category

CATEGORY_BY_FILENAME = {
    "general.md": Category.GENERAL,
    "rooms.md": Category.ROOMS,
    "amenities.md": Category.AMENITIES,
    "cancellation.md": Category.CANCELLATION,
    "pet-policy.md": Category.PET_POLICY,
    "check-in-check-out.md": Category.CHECK_IN_CHECK_OUT,
}

HOTEL_CATEGORIES = frozenset(
    {Category.GENERAL, Category.ROOMS, Category.AMENITIES, Category.CANCELLATION, Category.PET_POLICY}
)
KNOWN_CATEGORIES = frozenset(Category)

ALLOWED_KEYS = frozenset({"doc_id", "category", "title", "hotel_id", "destination_id"})


@dataclass(frozen=True)
class KnowledgeDocument:
    doc_id: str
    category: Category
    title: str
    hotel_id: str | None
    destination_id: str | None
    source_path: str
    body: str


def parse_frontmatter(text: str, source: str) -> dict[str, str]:
    fields = _parse_frontmatter_fields(text, source)
    _validate_frontmatter_keys(fields, source)
    _validate_frontmatter_scope(fields, source)
    return fields


def _parse_frontmatter_fields(text: str, source: str) -> dict[str, str]:
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
    return fields


def _validate_frontmatter_keys(fields: dict[str, str], source: str) -> None:
    unknown = sorted(set(fields) - ALLOWED_KEYS)
    if unknown:
        raise RagError(f"{source}: unknown frontmatter keys {', '.join(unknown)}")
    for required in ("doc_id", "category", "title"):
        if not fields.get(required):
            raise RagError(f"{source}: frontmatter key {required!r} is required")
    if fields["category"] not in KNOWN_CATEGORIES:
        raise RagError(f"{source}: unknown category {fields['category']!r}")


def _validate_frontmatter_scope(fields: dict[str, str], source: str) -> None:
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


def load_corpus(corpus_path: Path) -> list[KnowledgeDocument]:
    if not corpus_path.is_dir():
        raise RagError(f"knowledge corpus path not found: {corpus_path}")
    files = sorted(p for p in corpus_path.rglob("*.md") if p.is_file())
    documents: list[KnowledgeDocument] = []
    seen: set[str] = set()
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise RagError(f"{path.relative_to(corpus_path).as_posix()}: unreadable document ({exc})") from exc
        relative = path.relative_to(corpus_path).as_posix()
        fields = parse_frontmatter(text, relative)
        filename = path.name
        if filename not in CATEGORY_BY_FILENAME:
            raise RagError(f"{relative}: unrecognized knowledge document name")
        if fields["category"] != CATEGORY_BY_FILENAME[filename].value:
            raise RagError(f"{relative}: category {fields['category']!r} does not match file name {filename!r}")
        if fields["doc_id"] in seen:
            raise RagError(f"{relative}: duplicate doc_id {fields['doc_id']!r}")
        seen.add(fields["doc_id"])
        body = text.split("---", 2)[2].strip()
        documents.append(
            KnowledgeDocument(
                doc_id=fields["doc_id"],
                category=Category(fields["category"]),
                title=fields["title"],
                hotel_id=fields.get("hotel_id") or None,
                destination_id=fields.get("destination_id") or None,
                source_path=relative,
                body=body,
            )
        )
    return documents


def corpus_fingerprint(corpus_path: Path) -> str:
    if not corpus_path.is_dir():
        raise RagError(f"knowledge corpus path not found: {corpus_path}")
    digest = hashlib.sha256()
    for path in sorted(p for p in corpus_path.rglob("*.md") if p.is_file()):
        digest.update(path.relative_to(corpus_path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError as exc:
            raise RagError(f"{path.relative_to(corpus_path).as_posix()}: unreadable document ({exc})") from exc
        digest.update(b"\0")
    return digest.hexdigest()
