from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from services.search.http_shard_client import (
    HttpShardSearchClient,
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


def start_shard(
    *,
    shard_id: str,
    port: int,
    data_path: Path,
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


def stop_process(
    process: subprocess.Popen,
) -> None:
    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(
            timeout=10
        )
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(
            timeout=10
        )


def test_real_remote_shard_health(
    tmp_path,
):
    port = find_free_port()

    data_path = (
        tmp_path / "shard-0"
    )
    data_path.mkdir()

    process = start_shard(
        shard_id="shard-0",
        port=port,
        data_path=data_path,
    )

    base_url = (
        f"http://127.0.0.1:{port}"
    )

    try:
        wait_for_health(
            base_url=base_url,
            process=process,
        )

        client = HttpShardSearchClient(
            shard_id="shard-0",
            base_url=base_url,
        )

        assert client.health() is True

        stop_process(process)

        deadline = (
            time.monotonic()
            + 5
        )

        while (
            time.monotonic()
            < deadline
            and process.poll() is None
        ):
            time.sleep(0.1)

        assert client.health() is False

    finally:
        stop_process(process)