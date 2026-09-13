# Phase 3 — Real-World End-to-End Verification

This smoke test verifies the complete distributed indexing path using the actual local infrastructure:

```text
PostgreSQL
    ↓
Document Event Producer
    ↓
Kafka
    ↓
Indexer Worker
    ↓
Shard Router
    ↓
Remote Shard Service
    ↓
Persistent Search Index
    ↓
Shard Search API
```

The purpose is to verify that a real document update can travel through the complete distributed indexing pipeline and become searchable on the correct remote shard.

---

## Infrastructure

The test uses:

| Component  | Address          |
| ---------- | ---------------- |
| PostgreSQL | `localhost:5433` |
| Kafka      | `localhost:9092` |
| Shard 0    | `localhost:8100` |
| Shard 1    | `localhost:8101` |
| Shard 2    | `localhost:8102` |

The indexer worker runs locally:

```cmd
python -m services.indexer.worker_service
```

---

## 1. Start Infrastructure

From the project directory:

```cmd
docker compose up -d
```

Verify the containers:

```cmd
docker ps
```

Make sure PostgreSQL and Kafka are running.

---

## 2. Start Shard Services

Start all three shard services:

```text
shard-0 → 8100
shard-1 → 8101
shard-2 → 8102
```

Verify their health endpoints:

```cmd
curl http://127.0.0.1:8100/health
curl http://127.0.0.1:8101/health
curl http://127.0.0.1:8102/health
```

All three should return a healthy response.

---

## 3. Start the Search API

Start the existing FastAPI Search API.

Verify:

```cmd
curl http://127.0.0.1:8000/health
```

Optional checks:

```cmd
curl http://127.0.0.1:8000/db-test
curl http://127.0.0.1:8000/documents-count
```

---

## 4. Start the Indexer Worker

Open another CMD and run:

```cmd
python -m services.indexer.worker_service
```

Keep this terminal running.

The real distributed indexing path is:

```text
Kafka
  ↓
Indexer Worker
  ↓
ShardRouter
  ↓
HttpShardIndexClient
  ↓
Remote Shard Service
```

The worker must use the remote shard clients rather than an in-process `ShardManager`.

---

## 5. Create a Document Update Event

The real-world smoke test uses:

```text
tests/test_real_kafka.py
```

For the final verification, document `486` was updated from version `2` to version `3`.

The test marker was changed to:

```python
marker = (
    " Distributed Search Engine Kafka smoke test "
    "event verification version three."
)
```

Run:

```cmd
python tests/test_real_kafka.py
```

Expected result:

```text
Document ID      : 486
Current version  : 2
Storage result   : updated
New version      : 3

Kafka event:
  Event ID       : <new-event-id>
  Event type     : updated
  Document ID    : 486
  Event version  : 3

Kafka publish    : SUCCESS
```

The event ID will be different each time the test is recreated.

---

## 6. Verify the Kafka Event

List Kafka topics:

```cmd
docker exec search-engine-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

Expected topics include:

```text
__consumer_offsets
document-events
document-events-dlq
```

Consume the document event topic:

```cmd
docker exec -it search-engine-kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic document-events --from-beginning
```

Verify that the newly generated event exists with:

```text
document_id = 486
event_type = updated
event_version = 3
```

Stop the consumer with:

```text
Ctrl+C
```

---

## 7. Verify the Event Is Not in the DLQ

Consume the DLQ:

```cmd
docker exec -it search-engine-kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic document-events-dlq --from-beginning
```

The newly generated version-3 event should **not** appear in the DLQ.

Stop the consumer:

```text
Ctrl+C
```

---

## 8. Determine the Document's Shard

The project uses consistent hashing for document-to-shard routing.

Run:

```cmd
python -c "from services.indexer.shard_manager import ShardManager; m=ShardManager(shard_ids=['shard-0','shard-1','shard-2']); print(m.get_shard_for_document(486).shard_id)"
```

For the verification above, the result was:

```text
shard-1
```

Therefore document `486` should be searchable through:

```text
http://127.0.0.1:8101
```

---

## 9. Verify Kafka Consumer Group

Check the indexer worker's Kafka consumer group:

```cmd
docker exec search-engine-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group indexer-workers
```

A healthy running worker should show an active consumer:

```text
CONSUMER-ID
rdkafka-...
```

and Kafka lag should eventually become:

```text
LAG = 0
```

Example successful state:

```text
PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
0          10              10              0
1          12              12              0
2          53              53              0
```

This confirms that the indexer worker consumed the pending Kafka events.

---

## 10. Verify PostgreSQL Index Version

Verify the document's indexed version and processed events.

Example:

```cmd
python -c "from services.search_api.database import SessionLocal; from libs.models.document_index_version import DocumentIndexVersion; from libs.models.processed_event import ProcessedEvent; db=SessionLocal(); print('INDEX VERSION:', [(x.document_id, x.event_version, x.event_id) for x in db.query(DocumentIndexVersion).filter_by(document_id=486).all()]); print('PROCESSED EVENTS:', [(x.document_id, x.event_version, x.event_id) for x in db.query(ProcessedEvent).filter_by(document_id=486).all()]); db.close()"
```

Successful output should show:

```text
INDEX VERSION:
[(486, 3, '<version-3-event-id>')]
```

and:

```text
PROCESSED EVENTS:
[
    (486, 2, '<version-2-event-id>'),
    (486, 3, '<version-3-event-id>')
]
```

This confirms that the worker processed the event and recorded the indexed version.

---

## 11. Verify the Remote Shard

Because document `486` maps to `shard-1`, query:

```cmd
curl "http://127.0.0.1:8101/search?q=version"
```

Expected response:

```json
{
    "shard_id": "shard-1",
    "results": [
        {
            "doc_id": 486,
            "score": 0.39556284962119864
        }
    ]
}
```

The exact score may vary depending on index contents.

The important verification is:

```text
shard_id = shard-1
doc_id   = 486
```

---

## Verification Checklist

The complete smoke test is successful when all of the following are true:

* [x] PostgreSQL running
* [x] Kafka running
* [x] All three shard services running
* [x] Search API running
* [x] Indexer worker running
* [x] Document updated in PostgreSQL
* [x] Kafka event published
* [x] Event exists in `document-events`
* [x] Event is not sent to DLQ
* [x] Kafka consumer group has an active member
* [x] Kafka lag reaches `0`
* [x] Document index version updated
* [x] Processed event recorded
* [x] Consistent hashing routes document to expected shard
* [x] Remote shard contains the document
* [x] Remote shard search returns the document

---

## End-to-End Result

The successful test proves:

```text
Document Update
      ↓
PostgreSQL
      ↓
DocumentChangeEvent
      ↓
Kafka
      ↓
Indexer Worker
      ↓
ShardRouter
      ↓
HTTP Remote Shard Client
      ↓
Shard-1
      ↓
Persistent BM25 Index
      ↓
Shard Search API
      ↓
Document 486 returned
```

This provides real-world verification of the Phase 3 distributed indexing architecture.

**Phase 3 is considered complete and frozen after this verification.**
