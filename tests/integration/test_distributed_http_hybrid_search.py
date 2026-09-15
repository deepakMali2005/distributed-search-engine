from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from services.search.coordinator import SearchCoordinator
from services.search.http_shard_client import HttpShardSearchClient
from services.semantic.models import Embedding


class DeterministicEmbeddingModel:
    """
    Small deterministic embedding model for integration tests.

    The production system uses Sentence Transformers. This test model keeps
    the integration test offline and deterministic while exercising the real
    HTTP shard boundary and distributed coordinator.
    """

    dimension = 3

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> Embedding:
        self.calls.append(text)

        normalized = text.lower()

        if "python" in normalized:
            return Embedding([1.0, 0.0, 0.0])

        if "kafka" in normalized:
            return Embedding([0.0, 1.0, 0.0])

        return Embedding([0.0, 0.0, 1.0])


def find_free_port() -> int:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(
    base_url: str,
    process: subprocess.Popen,
    timeout: float = 15.0,
) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                "Shard process exited before becoming healthy."
            )

        try:
            with urlopen(
                f"{base_url}/health",
                timeout=1,
            ) as response:
                if response.status == 200:
                    return
        except Exception:
            pass

        time.sleep(0.2)

    raise AssertionError(
        f"Shard at {base_url} did not become healthy."
    )


def start_shard(
    data_path: Path,
    shard_id: str,
    port: int,
) -> subprocess.Popen:
    environment = os.environ.copy()

    environment["SHARD_ID"] = shard_id
    environment["SHARD_HOST"] = "127.0.0.1"
    environment["SHARD_PORT"] = str(port)
    environment["SHARD_DATA_PATH"] = str(data_path)

    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.shard.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_process(
    process: subprocess.Popen,
) -> None:
    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def post_document(
    base_url: str,
    document_id: int,
    tokens: list[str],
    embedding: list[float],
) -> dict:
    payload = json.dumps(
        {
            "document_id": document_id,
            "tokens": tokens,
            "embedding": embedding,
        }
    ).encode("utf-8")

    request = Request(
        f"{base_url}/documents",
        data=payload,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(
        request,
        timeout=5,
    ) as response:
        assert response.status == 200

        return json.loads(
            response.read().decode("utf-8")
        )


def test_distributed_http_hybrid_search_across_three_real_shards(
    tmp_path,
):
    """
    Exercise the complete distributed hybrid path with real shard processes.

    Query -> coordinator -> HTTP lexical + semantic retrieval -> global
    HybridRanker -> final Top-K.
    """
    shard_configs = []
    processes = []

    try:
        for index in range(3):
            shard_id = f"shard-{index}"

            data_path = tmp_path / shard_id
            data_path.mkdir()

            port = find_free_port()

            process = start_shard(
                data_path=data_path,
                shard_id=shard_id,
                port=port,
            )

            processes.append(process)
            shard_configs.append(
                (
                    shard_id,
                    f"http://127.0.0.1:{port}",
                    process,
                )
            )

        for (
            shard_id,
            base_url,
            process,
        ) in shard_configs:
            wait_for_health(
                base_url=base_url,
                process=process,
            )

        # Shard 0: strong lexical + semantic match.
        post_document(
            shard_configs[0][1],
            9001,
            ["python", "search", "engine"],
            [1.0, 0.0, 0.0],
        )

        # Shard 1: semantic-only candidate for the query. The token is
        # deliberately different so lexical retrieval does not find it.
        post_document(
            shard_configs[1][1],
            9002,
            ["programming", "language"],
            [0.95, 0.0, 0.0],
        )

        # Shard 2: lexical candidate with weaker semantic similarity.
        post_document(
            shard_configs[2][1],
            9003,
            ["python", "tutorial"],
            [0.2, 0.0, 0.0],
        )

        clients = [
            HttpShardSearchClient(
                shard_id=shard_id,
                base_url=base_url,
                timeout_seconds=5,
            )
            for shard_id, base_url, _ in shard_configs
        ]

        embedding_model = DeterministicEmbeddingModel()

        coordinator = SearchCoordinator(
            shard_clients=clients,
            embedding_model=embedding_model,
            shard_timeout_seconds=5,
        )

        response = coordinator.hybrid_search(
            query="python",
            limit=10,
        )

        assert response.total_shards == 3
        assert response.successful_shards == 3
        assert response.failed_shards == 0
        assert response.timed_out_shards == 0
        assert response.is_partial is False

        assert embedding_model.calls == [
            "python"
        ]

        document_ids = [
            result.doc_id
            for result in response.results
        ]

        assert set(document_ids) == {
            9001,
            9002,
            9003,
        }

        assert document_ids[0] == 9001
        assert len(response.results) == 3

    finally:
        for process in processes:
            stop_process(process)


def test_distributed_http_hybrid_search_preserves_semantic_only_candidates(
    tmp_path,
):
    """
    Verify that a document absent from BM25 candidates can still enter the
    final result set through the semantic retrieval path over HTTP.
    """
    shard_configs = []
    processes = []

    try:
        for index in range(2):
            shard_id = f"semantic-shard-{index}"
            data_path = tmp_path / shard_id
            data_path.mkdir()

            port = find_free_port()
            process = start_shard(
                data_path=data_path,
                shard_id=shard_id,
                port=port,
            )

            processes.append(process)
            shard_configs.append(
                (
                    shard_id,
                    f"http://127.0.0.1:{port}",
                    process,
                )
            )

        for _, base_url, process in shard_configs:
            wait_for_health(
                base_url=base_url,
                process=process,
            )

        post_document(
            shard_configs[0][1],
            9101,
            ["python"],
            [1.0, 0.0, 0.0],
        )

        post_document(
            shard_configs[1][1],
            9102,
            ["programming", "language"],
            [0.99, 0.0, 0.0],
        )

        clients = [
            HttpShardSearchClient(
                shard_id=shard_id,
                base_url=base_url,
                timeout_seconds=5,
            )
            for shard_id, base_url, _ in shard_configs
        ]

        coordinator = SearchCoordinator(
            shard_clients=clients,
            embedding_model=DeterministicEmbeddingModel(),
            shard_timeout_seconds=5,
        )

        response = coordinator.hybrid_search(
            query="python",
            limit=10,
        )

        document_ids = {
            result.doc_id
            for result in response.results
        }

        assert 9101 in document_ids
        assert 9102 in document_ids
        assert response.is_partial is False

    finally:
        for process in processes:
            stop_process(process)
