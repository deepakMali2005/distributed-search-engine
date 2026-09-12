A Kafka-driven asynchronous indexing pipeline distributes document changes across indexer workers, consistent hashing assigns documents to persistent shard services, and a stateless search coordinator queries those shards in parallel and globally merges their results.


                         ┌─────────────────────┐
                         │      CRAWLER        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     PROCESSOR       │
                         │ clean / normalize   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │         POSTGRESQL           │
                    │     Document Source of Truth │
                    │                              │
                    │ document_id                  │
                    │ url                          │
                    │ content                      │
                    │ content_hash                 │
                    │ metadata                     │
                    └──────────────┬───────────────┘
                                   │
                      CREATED / UPDATED / DELETED
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     DOCUMENT EVENT PRODUCER  │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │            KAFKA             │
                    │                              │
                    │ document-events topic        │
                    │ key = document_id            │
                    └──────────────┬───────────────┘
                                   │
                         Consumer Group
                  ┌────────────────┼────────────────┐
                  │                │                │
                  ▼                ▼                ▼
          ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
          │ INDEXER     │  │ INDEXER     │  │ INDEXER     │
          │ WORKER 1    │  │ WORKER 2    │  │ WORKER N    │
          └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
                 │                │                │
                 └────────────────┼────────────────┘
                                  │
                                  ▼
                        ┌────────────────────┐
                        │    SHARD ROUTER    │
                        │ consistent hashing │
                        └─────────┬──────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
                  ▼               ▼               ▼
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │ SHARD 1      │ │ SHARD 2      │ │ SHARD N      │
          │              │ │              │ │              │
          │ Inverted     │ │ Inverted     │ │ Inverted     │
          │ Index        │ │ Index        │ │ Index        │
          │              │ │              │ │              │
          │ Persistent   │ │ Persistent   │ │ Persistent   │
          │ Segments     │ │ Segments     │ │ Segments     │
          └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                 │                │                │
                 ▼                ▼                ▼
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │ SHARD        │ │ SHARD        │ │ SHARD        │
          │ SERVICE 1    │ │ SERVICE 2    │ │ SERVICE N    │
          └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                 │                │                │
                 └────────────────┼────────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │   SEARCH COORDINATOR     │
                    │                          │
                    │ parallel shard queries   │
                    │ per-shard Top-K          │
                    │ timeout handling         │
                    │ partial results          │
                    │ deduplication            │
                    │ global Top-K merge       │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │       SEARCH API         │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │       NEXT.JS UI         │
                    └──────────────────────────┘