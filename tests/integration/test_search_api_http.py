from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient

from services.search.coordinator import SearchCoordinator
from services.search.http_shard_client import HttpShardSearchClient
from services.search_api import main
from services.semantic.models import Embedding


class DeterministicEmbeddingModel:
    """
    Small deterministic embedding model for API integration tests.

    This keeps the test offline and deterministic while still exercising:

        FastAPI -> SearchCoordinator -> HTTP shards -> semantic retrieval
    """

    dimension = 3

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> Embedding:
        self.calls.append(text)

        normalized = text.lower()

        if "python" in normalized:
            return Embedding(
                [1.0, 0.0, 0.0]
            )

        if "kafka" in normalized:
            return Embedding(
                [0.0, 1.0, 0.0]
            )

        return Embedding(
            [0.0, 0.0, 1.0]
        )


def find_free_port() -> int:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        sock.bind(
            ("127.0.0.1", 0)
        )

        return int(
            sock.getsockname()[1]
        )


def wait_for_health(
    base_url: str,
    process: subprocess.Popen,
    timeout: float = 15.0,
) -> None:
    deadline = (
        time.monotonic()
        + timeout
    )

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                "Shard process exited before "
                "becoming healthy."
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
        f"Shard at {base_url} did not "
        "become healthy."
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
    environment["SHARD_DATA_PATH"] = str(
        data_path
    )

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
    embedding: list[float] | None = None,
) -> dict:
    payload = {
        "document_id": document_id,
        "tokens": tokens,
    }

    if embedding is not None:
        payload["embedding"] = embedding

    request = Request(
        f"{base_url}/documents",
        data=json.dumps(payload).encode(
            "utf-8"
        ),
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
            response.read().decode(
                "utf-8"
            )
        )


def create_api_coordinator(
    shard_configs: list[tuple[str, str, subprocess.Popen]],
    *,
    embedding_model=None,
) -> SearchCoordinator:
    clients = [
        HttpShardSearchClient(
            shard_id=shard_id,
            base_url=base_url,
            timeout_seconds=3,
        )
        for (
            shard_id,
            base_url,
            _,
        ) in shard_configs
    ]

    return SearchCoordinator(
        shard_clients=clients,
        shard_timeout_seconds=3,
        allow_partial_results=True,
        embedding_model=embedding_model,
    )


def start_shards(
    tmp_path: Path,
    count: int,
):
    shard_configs = []
    processes = []

    for index in range(count):
        shard_id = f"api-shard-{index}"

        data_path = (
            tmp_path / shard_id
        )
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

    return shard_configs, processes


def configure_api(
    shard_configs,
    *,
    embedding_model=None,
) -> SearchCoordinator:
    coordinator = create_api_coordinator(
        shard_configs,
        embedding_model=embedding_model,
    )

    main.search_coordinator = coordinator

    return coordinator


def test_search_api_real_http_lexical_search(
    tmp_path,
):
    """
    Exercise:

        FastAPI /search
            -> SearchCoordinator
            -> HttpShardSearchClient
            -> real shard HTTP services
            -> lexical retrieval
    """
    shard_configs = []
    processes = []

    try:
        (
            shard_configs,
            processes,
        ) = start_shards(
            tmp_path,
            count=3,
        )

        post_document(
            shard_configs[0][1],
            11001,
            [
                "python",
                "search",
            ],
        )

        post_document(
            shard_configs[1][1],
            11002,
            [
                "python",
                "distributed",
                "search",
            ],
        )

        post_document(
            shard_configs[2][1],
            11003,
            [
                "kafka",
                "distributed",
            ],
        )

        coordinator = configure_api(
            shard_configs,
        )

        assert coordinator.shard_count == 3

        client = TestClient(
            main.app,
            raise_server_exceptions=True,
        )

        response = client.get(
            "/search",
            params={
                "q": "python",
                "mode": "lexical",
                "limit": 10,
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["query"] == "python"
        assert body["mode"] == "lexical"

        assert body["total_shards"] == 3
        assert body["successful_shards"] == 3
        assert body["failed_shards"] == 0
        assert body["timed_out_shards"] == 0
        assert body["partial"] is False

        result_ids = [
            result["doc_id"]
            for result in body["results"]
        ]

        assert set(result_ids) == {
            11001,
            11002,
        }

    finally:
        for process in processes:
            stop_process(process)


def test_search_api_real_http_semantic_search(
    tmp_path,
):
    """
    Exercise the real API semantic path:

        FastAPI
            -> SearchCoordinator
            -> query embedding
            -> HTTP shard semantic-search
            -> global semantic results
    """
    shard_configs = []
    processes = []

    try:
        (
            shard_configs,
            processes,
        ) = start_shards(
            tmp_path,
            count=3,
        )

        post_document(
            shard_configs[0][1],
            12001,
            [
                "python",
                "programming",
            ],
            embedding=[
                1.0,
                0.0,
                0.0,
            ],
        )

        post_document(
            shard_configs[1][1],
            12002,
            [
                "software",
                "development",
            ],
            embedding=[
                0.95,
                0.0,
                0.0,
            ],
        )

        post_document(
            shard_configs[2][1],
            12003,
            [
                "kafka",
                "streaming",
            ],
            embedding=[
                0.0,
                1.0,
                0.0,
            ],
        )

        embedding_model = (
            DeterministicEmbeddingModel()
        )

        configure_api(
            shard_configs,
            embedding_model=embedding_model,
        )

        client = TestClient(
            main.app,
            raise_server_exceptions=True,
        )

        response = client.get(
            "/search",
            params={
                "q": "python",
                "mode": "semantic",
                "limit": 10,
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["query"] == "python"
        assert body["mode"] == "semantic"

        assert body["total_shards"] == 3
        assert body["successful_shards"] == 3
        assert body["failed_shards"] == 0
        assert body["timed_out_shards"] == 0
        assert body["partial"] is False

        result_ids = [
            result["doc_id"]
            for result in body["results"]
        ]

        assert result_ids == [
            12001,
            12002,
            12003,
        ]

        assert embedding_model.calls == [
            "python"
        ]

    finally:
        for process in processes:
            stop_process(process)


def test_search_api_real_http_hybrid_search(
    tmp_path,
):
    """
    Exercise the complete real HTTP hybrid path through the Search API.
    """
    shard_configs = []
    processes = []

    try:
        (
            shard_configs,
            processes,
        ) = start_shards(
            tmp_path,
            count=3,
        )

        post_document(
            shard_configs[0][1],
            13001,
            [
                "python",
                "search",
                "engine",
            ],
            embedding=[
                1.0,
                0.0,
                0.0,
            ],
        )

        post_document(
            shard_configs[1][1],
            13002,
            [
                "programming",
                "language",
            ],
            embedding=[
                0.95,
                0.0,
                0.0,
            ],
        )

        post_document(
            shard_configs[2][1],
            13003,
            [
                "python",
                "tutorial",
            ],
            embedding=[
                0.2,
                0.0,
                0.0,
            ],
        )

        embedding_model = (
            DeterministicEmbeddingModel()
        )

        configure_api(
            shard_configs,
            embedding_model=embedding_model,
        )

        client = TestClient(
            main.app,
            raise_server_exceptions=True,
        )

        response = client.get(
            "/search",
            params={
                "q": "python",
                "mode": "hybrid",
                "limit": 10,
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["query"] == "python"
        assert body["mode"] == "hybrid"

        assert body["total_shards"] == 3
        assert body["successful_shards"] == 3
        assert body["failed_shards"] == 0
        assert body["timed_out_shards"] == 0
        assert body["partial"] is False

        result_ids = [
            result["doc_id"]
            for result in body["results"]
        ]

        assert set(result_ids) == {
            13001,
            13002,
            13003,
        }

        assert result_ids[0] == 13001

        assert embedding_model.calls == [
            "python"
        ]

    finally:
        for process in processes:
            stop_process(process)


def test_search_api_real_http_returns_partial_results_when_shard_fails(
    tmp_path,
):
    """
    Verify that the Search API preserves the coordinator's partial-result
    semantics when one real shard becomes unavailable.
    """
    shard_configs = []
    processes = []

    try:
        (
            shard_configs,
            processes,
        ) = start_shards(
            tmp_path,
            count=3,
        )

        post_document(
            shard_configs[0][1],
            14001,
            [
                "python",
                "search",
            ],
        )

        post_document(
            shard_configs[1][1],
            14002,
            [
                "python",
                "distributed",
            ],
        )

        post_document(
            shard_configs[2][1],
            14003,
            [
                "python",
                "engine",
            ],
        )

        configure_api(
            shard_configs,
        )

        stop_process(
            shard_configs[1][2]
        )

        client = TestClient(
            main.app,
            raise_server_exceptions=True,
        )

        response = client.get(
            "/search",
            params={
                "q": "python",
                "mode": "lexical",
                "limit": 10,
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["query"] == "python"
        assert body["mode"] == "lexical"

        assert body["total_shards"] == 3
        assert body["successful_shards"] == 2
        assert body["failed_shards"] == 1
        assert body["timed_out_shards"] == 0
        assert body["partial"] is True

        result_ids = [
            result["doc_id"]
            for result in body["results"]
        ]

        assert set(result_ids) == {
            14001,
            14003,
        }

        assert 14002 not in result_ids

    finally:
        for process in processes:
            stop_process(process)