# Distributed Search Engine

A distributed hybrid search engine built from scratch to understand how modern search systems work internally.

The project focuses on implementing the core components of a modern search engine rather than simply using an existing search platform or building another LLM wrapper.

The system starts with classical Information Retrieval techniques such as inverted indexes and BM25, and gradually evolves into a distributed search architecture with persistent indexes, sharding, Kafka-based indexing, semantic search, hybrid ranking, and production-style observability.

---

# Project Overview

Modern search engines need to process large amounts of documents, build efficient indexes, distribute data across multiple machines, execute queries in parallel, and return highly relevant results with low latency.

This project aims to build a simplified version of such a system from scratch.

The system will include:

* Web crawling
* Document processing
* Persistent document storage
* Information Retrieval
* Inverted indexing
* BM25 ranking
* Incremental indexing
* Persistent index segments
* Segment merging
* Data sharding
* Consistent hashing
* Distributed indexing
* Kafka-based event processing
* Distributed query execution
* Semantic search
* Hybrid lexical and semantic retrieval
* Fault tolerance
* Observability
* Search performance evaluation

The project is designed to run locally during development while using an architecture that can eventually scale across multiple processes or machines.

---

# System Architecture

The high-level architecture is designed around a pipeline that transforms web pages into searchable documents and eventually into distributed search results.

```text
Crawler
   │
   ▼
Processor
   │
   ▼
Document Storage
   │
   ▼
Indexing Pipeline
   │
   ▼
Distributed Index
   │
   ▼
Search Coordinator
   │
   ▼
Search Results
```

As the system evolves, the architecture will become event-driven and distributed:

```text
Crawler
   │
   ▼
Processor
   │
   ▼
PostgreSQL
   │
   ▼
Kafka
   │
   ▼
Indexer Workers
   │
   ▼
Shard Router
   │
   ├──────────────┬──────────────┐
   ▼              ▼              ▼
Shard 1        Shard 2        Shard 3
   │              │              │
   └──────────────┼──────────────┘
                  ▼
          Search Coordinator
                  │
                  ▼
            Result Aggregation
                  │
                  ▼
             Search API
                  │
                  ▼
             Search UI
```

---

# Core Design Principles

## Build From Fundamentals

The search engine will implement important search concepts directly instead of hiding everything behind third-party search engines.

This includes:

* Inverted indexes
* Term statistics
* BM25
* Query analysis
* Candidate retrieval
* Ranking
* Sharding
* Distributed query execution

---

## Modular Architecture

The system is divided into separate components with clearly defined responsibilities.

```text
Crawler
Processor
Storage
Indexer
Shard Manager
Search Engine
Search Coordinator
Search API
Frontend
```

Each component should be independently testable and replaceable.

---

## Distributed by Design

The project will begin on a local machine, but the architecture will be designed so that components can eventually run as independent services.

For example:

```text
Local Shard
     │
     ▼
Shard Interface
     ▲
     │
Remote Shard Service
```

The search coordinator should not need to know whether a shard is local or running on another machine.

---

## Persistent by Design

Indexes should survive process restarts.

The system will use persistent index segments and shard metadata so that search infrastructure can recover without rebuilding everything from scratch.

---

## Event-Driven Architecture

As the system becomes distributed, document changes will flow through Kafka events.

```text
            Document Change
                    │
                    ▼
                  Kafka
                    │
      ┬─────────────├──────────────┐
      ▼             ▼              ▼
Worker 1         Worker 2        Worker 3
      │              │              │
      └──────────────┼──────────────┘
                     ▼
                  Indexes
```

This allows indexing work to be distributed across multiple workers.

---

# 5 Phase Development Plan

## Phase 1 — Search Engine Fundamentals

### Goal

Understand the fundamentals of Information Retrieval and build a basic search engine from scratch.

### Topics

* Information Retrieval fundamentals
* Document representation
* Text normalization
* Tokenization
* Stopword removal
* Stemming
* Inverted Index
* Term Frequency
* Document Frequency
* Inverse Document Frequency
* TF-IDF
* BM25
* Query analysis
* Candidate retrieval
* Result ranking
* Basic Search API
* Unit testing

### Outcome

A functional classical search engine capable of indexing documents and retrieving relevant results using BM25.

---

# Phase 2 — Scalable Search Foundation

### Goal

Transform the basic search engine into a persistent and scalable search architecture.

### Topics

* Web Crawler
* Document Processor
* PostgreSQL Storage
* Document metadata
* Content hashing
* Change detection
* Incremental indexing
* Persistent index
* Immutable index segments
* Segment management
* Segment merging
* Shard abstraction
* Consistent hashing
* Shard routing
* Shard-local indexing
* Shard-local search
* Distributed Search Coordinator
* Persistent shards
* Shard manifests
* Shard lifecycle
* Shard recovery
* Automated testing

### Outcome

A persistent sharded search engine capable of distributing documents across multiple logical shards and executing searches across them.

---

# Phase 3 — Real Distributed System

### Goal

Move from a locally simulated distributed architecture to independently running distributed services.

### Topics

* Document Event Contract
* Event schemas
* Kafka infrastructure
* Kafka topics
* Kafka producers
* Kafka consumers
* Consumer groups
* Distributed indexer workers
* Partitioning
* Retry handling
* Dead Letter Queue
* Idempotent indexing
* Event ordering
* Event versioning
* Worker failure recovery
* Remote shard services
* HTTP communication
* gRPC communication
* Distributed query execution
* Query timeouts
* Query retries
* Service health checks

### Outcome

A real event-driven distributed search system where indexing work can be processed by multiple independent workers and search requests can execute across remote shard services.

---

# Phase 4 — Semantic & Hybrid Search

### Goal

Combine classical lexical search with semantic search to improve search relevance.

### Topics

* Embeddings
* Embedding models
* Document embedding generation
* Query embeddings
* Vector indexes
* Vector similarity search
* Semantic retrieval
* BM25 retrieval
* Hybrid retrieval
* Score normalization
* Hybrid ranking
* Search relevance evaluation
* Ranking experiments
* Optional reranking

### Search Architecture

```text
                    Query
                      │
             ┌────────┴────────┐
             ▼                 ▼
        BM25 Search      Semantic Search
             │                 │
             ▼                 ▼
       Lexical Results   Vector Results
             │                 │
             └────────┬────────┘
                      ▼
                Score Fusion
                      │
                      ▼
               Hybrid Ranking
                      │
                      ▼
                Final Results
```

### Outcome

A hybrid search engine capable of understanding both exact keyword matches and semantic similarity.

---

# Phase 5 — Production, Observability & UX

### Goal

Turn the system into a production-style distributed search platform that can be monitored, benchmarked, tested under failure, and demonstrated through a user interface.

### Topics

* Next.js Search UI
* Search result interface
* Search analytics
* Prometheus
* Grafana
* Structured logging
* Distributed tracing
* Health monitoring
* Metrics collection
* Load testing
* Search benchmarks
* Query latency measurement
* Indexing throughput measurement
* Failure simulation
* Fault testing
* Docker deployment
* Architecture documentation
* System design diagrams
* Performance evaluation
* Final demonstration

### Outcome

A complete distributed hybrid search engine with a user-facing interface, observability, performance benchmarks, and production-style infrastructure.

---

# Final System Vision

The final system will evolve through the following architecture:

```text
                         Web
                          │
                          ▼
                       Crawler
                          │
                          ▼
                      Processor
                          │
                          ▼
                     PostgreSQL
                          │
                          ▼
                    Kafka Cluster
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
        Indexer Worker  Indexer Worker  Indexer Worker
             │            │            │
             └────────────┼────────────┘
                          ▼
                     Shard Router
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
          Shard 1       Shard 2      Shard 3
             │            │            │
             ▼            ▼            ▼
        Persistent    Persistent    Persistent
          Index          Index         Index
             │            │            │
             └────────────┼────────────┘
                          ▼
                  Search Coordinator
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
          Shard 1       Shard 2      Shard 3
             │            │            │
             └────────────┼────────────┘
                          ▼
                   Result Aggregation
                          │
                          ▼
                    Hybrid Ranking
                          │
                          ▼
                      Search API
                          │
                          ▼
                     Next.js UI
```

---

# Search Flow

A search request will eventually follow this path:

```text
User Query
    │
    ▼
Search API
    │
    ▼
Query Analysis
    │
    ▼
Search Coordinator
    │
    ├──────────────┬──────────────┐
    ▼              ▼              ▼
 Shard 1        Shard 2        Shard 3
    │              │              │
    ▼              ▼              ▼
Local Retrieval  Local Retrieval  Local Retrieval
    │              │              │
    └──────────────┼──────────────┘
                   ▼
             Result Aggregation
                   │
                   ▼
             Hybrid Ranking
                   │
                   ▼
              Global Top-K
                   │
                   ▼
               User Results
```

---

# Indexing Flow

Document indexing will eventually follow an event-driven architecture:

```text
Web Page
   │
   ▼
Crawler
   │
   ▼
Processor
   │
   ▼
PostgreSQL
   │
   ▼
Document Event
   │
   ▼
Kafka
   │
   ▼
Indexer Worker
   │
   ▼
Shard Router
   │
   ▼
Target Shard
   │
   ▼
Index Segment
   │
   ▼
Persistent Storage
```

---

# Technology Stack

## Backend

* Python
* FastAPI
* SQLAlchemy

## Database

* PostgreSQL

## Distributed Systems

* Apache Kafka
* Consistent Hashing
* Sharding
* Distributed Workers
* Consumer Groups
* Distributed Query Execution

## Search

* Information Retrieval
* Inverted Index
* BM25
* Vector Search
* Semantic Search
* Hybrid Search

## Infrastructure

* Docker
* Docker Compose

## Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS

## Observability

* Prometheus
* Grafana
* Structured Logging
* Distributed Tracing

---

# Project Structure

The project follows a modular service-oriented structure.

```text
project/
│
├── services/
│   ├── crawler/
│   ├── processor/
│   ├── storage/
│   ├── indexer/
│   ├── search/
│   ├── search_api/
│   └── pipeline/
│
├── libs/
│   ├── common/
│   └── models/
│
├── tests/
│
├── frontend/
│
├── infrastructure/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

# Project Vision

The ultimate goal is to build a small but serious distributed search engine from first principles.

The project follows this progression:

```text
Information Retrieval
        │
        ▼
Inverted Index
        │
        ▼
BM25 Search
        │
        ▼
Persistent Index
        │
        ▼
Index Segments
        │
        ▼
Sharding
        │
        ▼
Distributed Search
        │
        ▼
Kafka-Based Indexing
        │
        ▼
Distributed Services
        │
        ▼
Semantic Search
        │
        ▼
Hybrid Search
        │
        ▼
Production-Style System
```

The focus is on understanding how search engines work internally, how indexing and querying can be distributed, and how a search system can evolve from a simple local implementation into a fault-tolerant distributed architecture.
