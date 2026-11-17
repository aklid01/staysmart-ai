import logging
import sys

from staysmart.config import Settings, configure_logging
from staysmart.rag.bootstrap import build_project_index

logger = logging.getLogger("staysmart")


def main(argv: list[str] | None = None) -> int:
    commands = list(sys.argv[1:] if argv is None else argv)
    if not commands or commands[0] != "ingest":
        print("usage: python -m staysmart.rag ingest", file=sys.stderr)
        return 2
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    index, _ = build_project_index(settings)
    logger.info("indexed %d chunks (dim %d) into %s", index.chunk_count, index.dim, settings.rag_index_path)
    print(f"ingested {index.chunk_count} chunks (dim {index.dim}) into {settings.rag_index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
