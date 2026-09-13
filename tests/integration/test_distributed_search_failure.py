from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

from services.search.coordinator import SearchCoordinator
from services.search.http_shard_client import HttpShardSearchClient


def find_free_port() -> int:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_shard(
    shard_id: str,
    port: int,
    data_path: Path,
) -> subprocess.Popen:
    env = os.environ.copy()
    env["SHARD_ID"] = shard_id
    env["SHARD_HOST"] = "127.0.0.1"
    env["SHARD_PORT"] = str(port)
    env["SHARD_DATA_PATH"] = str(data_path)

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
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_health(
    port: int,
    timeout_seconds: float = 10.0,
) -> bool:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        try:
            request = Request(
                f"http://127.0.0.1:{port}/health",
                method="GET",
            )

            with urlopen(
                request,
                timeout=0.5,
            ) as response:
                if response.status == 200:
                    payload = json.loads(
                        response.read().decode("utf-8")
                    )

                    if payload.get("status") == "ok":
                        return True

        except OSError:
            pass

        time.sleep(0.05)

    return False


def stop_process(
    process: subprocess.Popen | None,
) -> None:
    if process is None:
        return

    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def post_document(
    port: int,
    document_id: int,
    tokens: list[str],
) -> None:
    payload = json.dumps(
        {
            "document_id": document_id,
            "tokens": tokens,
        }
    ).encode("utf-8")

    request = Request(
        f"http://127.0.0.1:{port}/documents",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
        },
    )

    with urlopen(
        request,
        timeout=2,
    ) as response:
        assert response.status == 200


def test_search_returns_partial_results_when_one_shard_fails(
    tmp_path: Path,
) -> None:
    ports = [
        find_free_port(),
        find_free_port(),
        find_free_port(),
    ]

    processes: list[subprocess.Popen] = []

    try:
        for index, port in enumerate(ports):
            process = start_shard(
                shard_id=f"shard-{index}",
                port=port,
                data_path=tmp_path / f"shard-{index}",
            )

            processes.append(process)

        for port in ports:
            assert wait_for_health(port)

        post_document(
            ports[0],
            document_id=9001,
            tokens=[
                "distribut",
                "search",
            ],
        )

        post_document(
            ports[1],
            document_id=9002,
            tokens=[
                "distribut",
                "search",
                "engin",
            ],
        )

        post_document(
            ports[2],
            document_id=9003,
            tokens=[
                "distribut",
                "search",
                "engin",
            ],
        )

        clients = [
            HttpShardSearchClient(
                shard_id=f"shard-{index}",
                base_url=f"http://127.0.0.1:{port}",
                timeout_seconds=1.0,
            )
            for index, port in enumerate(ports)
        ]

        stop_process(processes[1])
        processes[1] = None

        coordinator = SearchCoordinator(
            shard_clients=clients,
            shard_timeout_seconds=1.0,
            allow_partial_results=True,
        )

        response = coordinator.search(
            "distributed",
            limit=10,
        )

        assert response.total_shards == 3
        assert response.successful_shards == 2
        assert (
            response.failed_shards
            + response.timed_out_shards
            == 1
        )

        assert response.is_partial is True

        document_ids = {
            result.doc_id
            for result in response.results
        }

        assert document_ids == {
            9001,
            9003,
        }

        assert 9002 not in document_ids

    finally:
        for process in processes:
            stop_process(process)


def test_search_retries_transient_shard_failure_and_recovers(
    tmp_path: Path,
) -> None:
    ports = [
        find_free_port(),
        find_free_port(),
        find_free_port(),
    ]

    processes: list[subprocess.Popen | None] = [
        None,
        None,
        None,
    ]

    try:
        for index, port in enumerate(ports):
            processes[index] = start_shard(
                shard_id=f"shard-{index}",
                port=port,
                data_path=tmp_path / f"shard-{index}",
            )

        for port in ports:
            assert wait_for_health(port)

        post_document(
            ports[0],
            document_id=9101,
            tokens=[
                "distribut",
                "search",
            ],
        )

        post_document(
            ports[1],
            document_id=9102,
            tokens=[
                "distribut",
                "search",
                "engin",
            ],
        )

        post_document(
            ports[2],
            document_id=9103,
            tokens=[
                "distribut",
                "search",
                "engin",
            ],
        )

        clients = [
            HttpShardSearchClient(
                shard_id=f"shard-{index}",
                base_url=f"http://127.0.0.1:{port}",
                timeout_seconds=0.5,
            )
            for index, port in enumerate(ports)
        ]

        #
        # Create a real transient availability failure.
        #
        # shard-1 is stopped before the search begins.
        #
        stop_process(processes[1])
        processes[1] = None

        #
        # Restart shard-1 while the coordinator is retrying.
        #
        def restart_shard() -> None:
            time.sleep(0.3)

            processes[1] = start_shard(
                shard_id="shard-1",
                port=ports[1],
                data_path=tmp_path / "shard-1",
            )

        restart_thread = threading.Thread(
            target=restart_shard,
            daemon=True,
        )

        restart_thread.start()

        coordinator = SearchCoordinator(
            shard_clients=clients,
            shard_timeout_seconds=4.0,
            allow_partial_results=True,
            max_retries=5,
            retry_backoff_seconds=0.2,
        )

        response = coordinator.search(
            "distributed",
            limit=10,
        )

        restart_thread.join(timeout=5)

        assert processes[1] is not None
        assert wait_for_health(
            ports[1],
            timeout_seconds=5.0,
        )

        #
        # The transient failure should have recovered.
        #
        assert response.total_shards == 3
        assert response.successful_shards == 3
        assert response.failed_shards == 0
        assert response.timed_out_shards == 0
        assert response.is_partial is False

        document_ids = {
            result.doc_id
            for result in response.results
        }

        assert document_ids == {
            9101,
            9102,
            9103,
        }

    finally:
        for process in processes:
            stop_process(process)