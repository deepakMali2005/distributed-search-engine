from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from services.indexer.index import InvertedIndex, Posting
from services.indexer.segment import (
    IndexSegment,
    SegmentReader,
    SegmentWriter,
)
from services.indexer.shard import Shard
from services.indexer.shard_lifecycle import ShardLifecycleState
from services.indexer.shard_manifest import ShardManifest


class JsonShardPersistence:
    """
    Persist each shard as immutable segments plus an atomic manifest.

    A new segment is fully written before the manifest is replaced.

    The manifest therefore acts as the publication point for a
    shard generation.

    Older segments remain on disk until an explicit cleanup
    policy is added.
    """

    MANIFEST_NAME = "manifest.json"
    SEGMENTS_DIRECTORY = "segments"

    def __init__(
        self,
        root_directory: str | Path = "data/index/shards",
    ) -> None:
        self.root_directory = Path(root_directory)

        self.writer = SegmentWriter()
        self.reader = SegmentReader()

    def shard_directory(self, shard_id: str) -> Path:
        self._validate_shard_id(shard_id)

        return self.root_directory / shard_id

    def manifest_path(self, shard_id: str) -> Path:
        return (
            self.shard_directory(shard_id)
            / self.MANIFEST_NAME
        )

    def exists(self, shard_id: str) -> bool:
        return self.manifest_path(shard_id).is_file()

    def read_manifest(
        self,
        shard_id: str,
    ) -> ShardManifest:
        path = self.manifest_path(shard_id)

        if not path.is_file():
            raise FileNotFoundError(path)

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        manifest = ShardManifest.from_dict(payload)

        if manifest.shard_id != shard_id:
            raise ValueError(
                f"Shard manifest belongs to "
                f"{manifest.shard_id!r}, not {shard_id!r}."
            )

        return manifest

    def save(self, shard: Shard) -> ShardManifest:
        """
        Persist the current shard state.

        The segment is written first.

        Only after the segment is safely written do we
        atomically replace the manifest.
        """

        shard.set_lifecycle_state(
            ShardLifecycleState.PERSISTING
        )

        try:
            shard_dir = self.shard_directory(
                shard.shard_id
            )

            segments_dir = (
                shard_dir / self.SEGMENTS_DIRECTORY
            )

            segments_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            previous_generation = -1

            if self.exists(shard.shard_id):
                previous_generation = (
                    self.read_manifest(
                        shard.shard_id
                    ).generation
                )

            generation = previous_generation + 1

            segment_id = (
                f"segment-{generation:06d}"
            )

            segment = IndexSegment(
                segment_id=segment_id,
                path=(
                    segments_dir
                    / f"{segment_id}.json"
                ),
            )

            # 1. Write immutable segment.
            self.writer.write(
                index=shard.index,
                segment=segment,
            )

            # 2. Build new manifest.
            manifest = ShardManifest(
                shard_id=shard.shard_id,
                generation=generation,
                state=ShardLifecycleState.READY,
                active_segments=(segment_id,),
                document_count=shard.document_count,
            )

            # 3. Publish the new generation atomically.
            self._write_manifest_atomically(
                manifest
            )

            shard.set_lifecycle_state(
                ShardLifecycleState.READY
            )

            return manifest

        except Exception:
            shard.set_lifecycle_state(
                ShardLifecycleState.FAILED
            )
            raise

    def load(self, shard: Shard) -> bool:
        """
        Load the currently published shard generation.

        Returns:
            True  -> shard existed and was loaded.
            False -> no persisted shard exists.
        """

        if not self.exists(shard.shard_id):
            shard.set_lifecycle_state(
                ShardLifecycleState.NEW
            )
            return False

        shard.set_lifecycle_state(
            ShardLifecycleState.LOADING
        )

        try:
            manifest = self.read_manifest(
                shard.shard_id
            )

            shard.index.clear()

            segments_dir = (
                self.shard_directory(shard.shard_id)
                / self.SEGMENTS_DIRECTORY
            )

            for segment_id in manifest.active_segments:
                segment = IndexSegment(
                    segment_id=segment_id,
                    path=(
                        segments_dir
                        / f"{segment_id}.json"
                    ),
                )

                if not segment.path.is_file():
                    raise FileNotFoundError(
                        segment.path
                    )

                loaded_index = self.reader.read(
                    segment
                )

                self._merge_index(
                    target=shard.index,
                    source=loaded_index,
                )

            if (
                shard.document_count
                != manifest.document_count
            ):
                raise ValueError(
                    f"Shard {shard.shard_id} "
                    "document count does not match "
                    "its manifest."
                )

            shard.set_lifecycle_state(
                ShardLifecycleState.READY
            )

            return True

        except Exception:
            shard.set_lifecycle_state(
                ShardLifecycleState.FAILED
            )
            raise

    def delete(self, shard_id: str) -> bool:
        directory = self.shard_directory(
            shard_id
        )

        if not directory.exists():
            return False

        for path in sorted(
            directory.rglob("*"),
            reverse=True,
        ):
            if path.is_file() or path.is_symlink():
                path.unlink()

            elif path.is_dir():
                path.rmdir()

        directory.rmdir()

        return True

    def _write_manifest_atomically(
        self,
        manifest: ShardManifest,
    ) -> None:
        path = self.manifest_path(
            manifest.shard_id
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    manifest.to_dict(),
                    file,
                    separators=(",", ":"),
                )

                file.flush()
                os.fsync(file.fileno())

            os.replace(
                temp_name,
                path,
            )

        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    @staticmethod
    def _merge_index(
        target: InvertedIndex,
        source: InvertedIndex,
    ) -> None:
        for doc_id, length in (
            source.document_lengths.items()
        ):
            target.set_document_length(
                doc_id,
                length,
            )

        for term in source.terms:
            for posting in source.get_postings(term):
                target.set_posting(
                    term,
                    Posting(
                        doc_id=posting.doc_id,
                        term_frequency=posting.term_frequency,
                        positions=list(
                            posting.positions
                        ),
                    ),
                )

    @staticmethod
    def _validate_shard_id(
        shard_id: str,
    ) -> None:
        if not shard_id:
            raise ValueError(
                "shard_id cannot be empty."
            )

        if Path(shard_id).name != shard_id:
            raise ValueError(
                "shard_id cannot contain path separators."
            )