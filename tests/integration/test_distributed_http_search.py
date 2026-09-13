from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen


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
) -> dict:
    payload = json.dumps(
        {
            "document_id": document_id,
            "tokens": tokens,
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


class RemoteShard:
    """
    Minimal HTTP client implementing the coordinator's
    ShardSearchClient protocol.
    """

    def __init__(
        self,
        shard_id: str,
        base_url: str,
    ) -> None:
        self.shard_id = shard_id
        self.base_url = base_url.rstrip("/")

    def search(
        self,
        query: str,
        limit: int,
    ):
        from services.search.models import SearchResult
        from urllib.parse import quote

        url = (
            f"{self.base_url}/search"
            f"?q={quote(query, safe='')}"
            f"&limit={limit}"
        )

        with urlopen(
            url,
            timeout=5,
        ) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )

        return [
            SearchResult(
                doc_id=result["doc_id"],
                score=result["score"],
            )
            for result in payload["results"]
        ]


def test_distributed_search_across_three_real_shards(
    tmp_path,
):
    """
    Prove that SearchCoordinator can query three independent
    HTTP shard processes and globally merge their results.
    """
    shard_configs = []

    processes = []

    try:
        for index in range(3):
            shard_id = f"shard-{index}"

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

        post_document(
            shard_configs[0][1],
            8001,
            [
                "distribut",
                "search",
            ],
        )

        post_document(
            shard_configs[1][1],
            8002,
            [
                "distribut",
                "search",
                "engin",
            ],
        )

        post_document(
            shard_configs[2][1],
            8003,
            [
                "distribut",
                "search",
                "engin",
                "engin",
            ],
        )

        from services.search.coordinator import (
            SearchCoordinator,
        )

        clients = [
            RemoteShard(
                shard_id=shard_id,
                base_url=base_url,
            )
            for shard_id, base_url, _ in shard_configs
        ]

        coordinator = SearchCoordinator(
            shard_clients=clients,
        )

        response = coordinator.search(
            query="distributed",
            limit=10,
        )

        assert response.total_shards == 3
        assert response.successful_shards == 3
        assert response.failed_shards == 0
        assert response.timed_out_shards == 0
        assert response.is_partial is False

        document_ids = [
            result.doc_id
            for result in response.results
        ]

        assert set(document_ids) == {
            8001,
            8002,
            8003,
        }

        assert len(response.results) == 3

    finally:
        for process in processes:
            stop_process(process)