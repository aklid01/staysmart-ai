import logging
import sys

from staysmart.config import Settings, configure_logging
from staysmart.providers.mock.dataset import load_dataset
from staysmart.rag.embedder import FastEmbedEmbedder
from staysmart.rag.ingest import build_index

logger = logging.getLogger("staysmart")


def main(argv: list[str] | None = None) -> int:
    commands = list(sys.argv[1:] if argv is None else argv)
    if not commands or commands[0] != "ingest":
        print("usage: python -m staysmart.rag ingest", file=sys.stderr)
        return 2
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    dataset = load_dataset(settings.dataset_path)
    destination_by_hotel = {hotel.hotel_id: hotel.destination_id for hotel in dataset.hotels}
    embedder = FastEmbedEmbedder(settings.rag_model)
    index = build_index(
        settings.rag_corpus_path,
        settings.rag_index_path,
        embedder,
        destination_by_hotel=destination_by_hotel,
    )
    logger.info("indexed %d chunks (dim %d) into %s", index.chunk_count, index.dim, settings.rag_index_path)
    print(f"ingested {index.chunk_count} chunks (dim {index.dim}) into {settings.rag_index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
