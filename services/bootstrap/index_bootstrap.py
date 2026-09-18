from __future__ import annotations

import os

from sqlalchemy.orm import Session

from services.indexer.analyzer import TextAnalyzer
from services.indexer.remote_shard_client import HttpShardIndexClient
from services.indexer.shard_router import ShardRouter
from services.semantic.embedding import SentenceTransformerEmbeddingModel
from services.semantic.models import Embedding
from services.storage.storage import get_all_documents


DEFAULT_SHARD_URLS = {
    "shard-0": "http://127.0.0.1:8100",
    "shard-1": "http://127.0.0.1:8101",
    "shard-2": "http://127.0.0.1:8102",
}


class IndexBootstrapper:
    """
    Reconcile canonical PostgreSQL documents with distributed shards.

    Bootstrap is a specialized bulk-repair path. Normal document changes
    continue to use:

        PostgreSQL -> Kafka -> IndexerWorker -> shard

    Bootstrap does not publish thousands of one-document Kafka repair
    events. Instead, it analyzes, embeds, and indexes bounded batches
    directly through the shard bulk API.

    This dramatically reduces:
        - embedding model calls
        - HTTP requests
        - shard persistence publications
        - bootstrap startup time
    """

    def __init__(
        self,
        db: Session,
        shard_router: ShardRouter,
        shard_clients: dict[str, HttpShardIndexClient],
        *,
        embedding_model: SentenceTransformerEmbeddingModel | None = None,
        analyzer: TextAnalyzer | None = None,
        batch_size: int = 100,
    ) -> None:
        if not shard_clients:
            raise ValueError(
                "shard_clients cannot be empty."
            )

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero."
            )

        self.db = db
        self.shard_router = shard_router
        self.shard_clients = shard_clients
        self.analyzer = analyzer or TextAnalyzer()
        self.embedding_model = embedding_model
        self.batch_size = batch_size

    @staticmethod
    def _build_lexical_text(
        title: str | None,
        content: str,
    ) -> str:
        """
        Build the same lexical text representation used by the
        normal Kafka indexer.
        """

        title = (title or "").strip()
        content = (content or "").strip()

        if title and content:
            return f"{title}\n{content}"

        return title or content

    def find_missing_documents(self) -> list[int]:
        """
        Return document IDs that are not currently present on
        their owning shards.
        """

        missing_document_ids: list[int] = []

        for document in get_all_documents(self.db):
            shard_id = self.shard_router.get_shard_id(
                document.id
            )

            client = self.shard_clients.get(
                shard_id
            )

            if client is None:
                raise RuntimeError(
                    f"No shard client configured for {shard_id}"
                )

            if not client.contains_document(
                document.id
            ):
                missing_document_ids.append(
                    document.id
                )

        return missing_document_ids

    def bootstrap(
        self,
        document_ids: list[int],
    ) -> int:
        """
        Bulk-index the supplied PostgreSQL documents.

        Documents are:
            1. grouped by owning shard
            2. analyzed in bounded batches
            3. embedded in batches
            4. sent to the shard using one bulk HTTP request
            5. persisted once per batch

        Documents with empty content are indexed lexically but do not
        receive a semantic embedding. This prevents invalid empty strings
        from reaching the sentence-transformer model.

        Returns the number of successfully indexed documents.
        """

        if not document_ids:
            return 0

        documents_by_id = {
            document.id: document
            for document in get_all_documents(self.db)
        }

        grouped_documents: dict[str, list] = {
            shard_id: []
            for shard_id in self.shard_clients
        }

        for document_id in document_ids:
            document = documents_by_id.get(
                document_id
            )

            if document is None:
                raise RuntimeError(
                    f"Document {document_id} does not exist in PostgreSQL."
                )

            shard_id = self.shard_router.get_shard_id(
                document_id
            )

            if shard_id not in self.shard_clients:
                raise RuntimeError(
                    f"No shard client configured for {shard_id}"
                )

            grouped_documents[shard_id].append(
                document
            )

        indexed_count = 0

        for shard_id, documents in grouped_documents.items():
            if not documents:
                continue

            client = self.shard_clients[
                shard_id
            ]

            for start in range(
                0,
                len(documents),
                self.batch_size,
            ):
                batch = documents[
                    start : start + self.batch_size
                ]

                token_lists = [
                    self.analyzer.analyze(
                        self._build_lexical_text(
                            title=document.title,
                            content=document.content,
                        )
                    )
                    for document in batch
                ]

                embeddings: list[
                    Embedding | None
                ] = [None] * len(batch)

                if self.embedding_model is not None:
                    non_empty_documents = [
                        (
                            index,
                            document,
                        )
                        for index, document in enumerate(batch)
                        if (document.content or "").strip()
                    ]

                    if non_empty_documents:
                        non_empty_embeddings = (
                            self.embedding_model.embed_batch(
                                [
                                    document.content
                                    for _, document in non_empty_documents
                                ]
                            )
                        )

                        if len(non_empty_embeddings) != len(
                            non_empty_documents
                        ):
                            raise RuntimeError(
                                "Embedding model returned an unexpected "
                                "number of embeddings."
                            )

                        for (
                            (document_index, _),
                            embedding,
                        ) in zip(
                            non_empty_documents,
                            non_empty_embeddings,
                        ):
                            embeddings[document_index] = embedding

                client.index_documents(
                    [
                        (
                            document.id,
                            tokens,
                            embedding,
                        )
                        for document, tokens, embedding in zip(
                            batch,
                            token_lists,
                            embeddings,
                        )
                    ]
                )

                indexed_count += len(batch)

                print(
                    "Bootstrap indexed "
                    f"{indexed_count}/{len(document_ids)} "
                    "documents "
                    f"(shard={shard_id}, "
                    f"batch={len(batch)})."
                )

        return indexed_count


def _load_shard_urls() -> dict[str, str]:
    raw = os.getenv(
        "INDEXER_SHARD_URLS"
    )

    if not raw:
        return dict(
            DEFAULT_SHARD_URLS
        )

    shard_urls: dict[str, str] = {}

    for item in raw.split(","):
        item = item.strip()

        if not item:
            continue

        if "=" not in item:
            raise ValueError(
                "INDEXER_SHARD_URLS entries must use "
                "shard-id=url format."
            )

        shard_id, url = item.split(
            "=",
            1,
        )

        shard_id = shard_id.strip()
        url = url.strip()

        if not shard_id:
            raise ValueError(
                "Shard ID cannot be empty."
            )

        if not url:
            raise ValueError(
                f"URL cannot be empty for {shard_id}."
            )

        shard_urls[shard_id] = url

    if not shard_urls:
        raise ValueError(
            "INDEXER_SHARD_URLS cannot be empty."
        )

    return shard_urls


def main() -> None:
    from services.search_api.database import SessionLocal

    db = SessionLocal()

    try:
        shard_urls = _load_shard_urls()

        router = ShardRouter(
            shard_ids=list(shard_urls)
        )

        shard_timeout = float(
            os.getenv(
                "INDEX_BOOTSTRAP_SHARD_TIMEOUT_SECONDS",
                "60",
            )
        )

        clients = {
            shard_id: HttpShardIndexClient(
                shard_id=shard_id,
                base_url=url,
                timeout_seconds=shard_timeout,
            )
            for shard_id, url in shard_urls.items()
        }

        embedding_model = (
            SentenceTransformerEmbeddingModel()
        )

        bootstrapper = IndexBootstrapper(
            db=db,
            shard_router=router,
            shard_clients=clients,
            embedding_model=embedding_model,
            batch_size=int(
                os.getenv(
                    "INDEX_BOOTSTRAP_BATCH_SIZE",
                    "100",
                )
            ),
        )

        missing_document_ids = (
            bootstrapper.find_missing_documents()
        )

        if not missing_document_ids:
            print(
                "Index bootstrap completed: "
                "0 documents required repair."
            )
            return

        indexed = bootstrapper.bootstrap(
            missing_document_ids
        )

        if indexed != len(
            missing_document_ids
        ):
            raise RuntimeError(
                "Bootstrap did not index every "
                "missing document: "
                f"indexed={indexed}, "
                f"missing={len(missing_document_ids)}"
            )

        print(
            "Index bootstrap completed: "
            f"{indexed} document(s) repaired."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()