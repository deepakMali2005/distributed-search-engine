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
    """
    Ask the OS for an available local TCP port.
    """
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
    """
    Wait until the shard process responds to /health.
    """
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                "Shard process exited before becoming healthy."
            )

        try:
            response = urlopen(
                f"{base_url}/health",
                timeout=1,
            )

            if response.status == 200:
                return

        except Exception:
            pass

        time.sleep(0.2)

    raise AssertionError(
        "Shard process did not become healthy within "
        f"{timeout} seconds."
    )


def start_shard_process(
    data_path: Path,
    port: int,
) -> subprocess.Popen:
    """
    Start an independent Uvicorn shard process.
    """
    environment = os.environ.copy()

    environment["SHARD_ID"] = "process-test-shard"
    environment["SHARD_HOST"] = "127.0.0.1"
    environment["SHARD_PORT"] = str(port)
    environment["SHARD_DATA_PATH"] = str(data_path)

    process = subprocess.Popen(
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

    return process


def stop_shard_process(
    process: subprocess.Popen,
) -> None:
    """
    Terminate a shard process and force-kill it if necessary.
    """
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
    """
    Index an already-analyzed document through the HTTP shard API.

    The shard service receives analyzed tokens from the distributed
    indexer worker. Document analysis/stemming is intentionally
    performed before the shard boundary.
    """
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


def search(
    base_url: str,
    query: str,
) -> dict:
    """
    Search the shard through its HTTP API.
    """
    encoded_query = (
        query.replace("%", "%25")
        .replace(" ", "%20")
    )

    with urlopen(
        f"{base_url}/search?q={encoded_query}&limit=10",
        timeout=5,
    ) as response:
        assert response.status == 200

        return json.loads(
            response.read().decode("utf-8")
        )


def test_shard_persists_across_real_process_restart(
    tmp_path,
):
    """
    Prove that a document indexed by one shard process
    survives termination and is searchable by a completely
    new shard process using the same persistent data directory.
    """
    data_path = tmp_path / "shard-data"
    data_path.mkdir()

    port = find_free_port()

    base_url = (
        f"http://127.0.0.1:{port}"
    )

    first_process = start_shard_process(
        data_path=data_path,
        port=port,
    )

    second_process = None

    try:
        wait_for_health(
            base_url=base_url,
            process=first_process,
        )

        response = post_document(
            base_url=base_url,
            document_id=7001,
            tokens=[
                "distribut",
                "search",
                "engin",
            ],
        )

        assert response["shard_id"] == (
            "process-test-shard"
        )

        assert response["document_id"] == 7001

        first_search = search(
            base_url=base_url,
            query="distributed",
        )

        first_document_ids = [
            result["doc_id"]
            for result in first_search["results"]
        ]

        assert 7001 in first_document_ids

    finally:
        stop_shard_process(
            first_process
        )

    second_process = start_shard_process(
        data_path=data_path,
        port=port,
    )

    try:
        wait_for_health(
            base_url=base_url,
            process=second_process,
        )

        second_search = search(
            base_url=base_url,
            query="distributed",
        )

        second_document_ids = [
            result["doc_id"]
            for result in second_search["results"]
        ]

        assert 7001 in second_document_ids

    finally:
        stop_shard_process(
            second_process
        )