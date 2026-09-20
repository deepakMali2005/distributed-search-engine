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
    Persist each shard as immutable lexical + semantic segments plus
    an atomic manifest.

    A new segment is fully written before the manifest is replaced.
    The manifest therefore remains the publication point for a shard
    generation.

    Only segments referenced by the published manifest are retained.
    Older unreferenced generations are garbage-collected after the
    new manifest has been published successfully.
    """

    MANIFEST_NAME = "manifest.json"
    SEGMENTS_DIRECTORY = "segments"
    SEGMENT_SUFFIX = ".json"
    TEMP_SEGMENT_SUFFIX = ".json.tmp"

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
        return self.shard_directory(shard_id) / self.MANIFEST_NAME

    def segments_directory(self, shard_id: str) -> Path:
        return (
            self.shard_directory(shard_id)
            / self.SEGMENTS_DIRECTORY
        )

    def exists(self, shard_id: str) -> bool:
        return self.manifest_path(shard_id).is_file()

    def read_manifest(self, shard_id: str) -> ShardManifest:
        path = self.manifest_path(shard_id)

        if not path.is_file():
            raise FileNotFoundError(path)

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        manifest = ShardManifest.from_dict(payload)

        if manifest.shard_id != shard_id:
            raise ValueError(
                f"Shard manifest belongs to {manifest.shard_id!r}, "
                f"not {shard_id!r}."
            )

        return manifest

    def save(self, shard: Shard) -> ShardManifest:
        """
        Persist the complete current shard state.

        The new segment is written first. The manifest is then atomically
        replaced to publish the new generation. Only after successful
        publication are obsolete segments removed.

        If cleanup fails, the newly published generation remains valid and
        stale files can be cleaned up during a later save/load.
        """
        shard.set_lifecycle_state(
            ShardLifecycleState.PERSISTING
        )

        try:
            shard_dir = self.shard_directory(
                shard.shard_id
            )

            segments_dir = self.segments_directory(
                shard.shard_id
            )

            segments_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            previous_generation = -1

            if self.exists(shard.shard_id):
                previous_generation = self.read_manifest(
                    shard.shard_id
                ).generation

            generation = previous_generation + 1
            segment_id = f"segment-{generation:06d}"

            segment = IndexSegment(
                segment_id=segment_id,
                path=segments_dir / f"{segment_id}.json",
            )

            self.writer.write(
                index=shard.index,
                segment=segment,
                vector_index=shard.vector_index,
            )

            manifest = ShardManifest(
                shard_id=shard.shard_id,
                generation=generation,
                state=ShardLifecycleState.READY,
                active_segments=(segment_id,),
                document_count=shard.document_count,
            )

            # Publication point.
            #
            # Once this succeeds, the new segment is the authoritative
            # shard generation.
            self._write_manifest_atomically(
                manifest
            )

            # The new generation is now durable and published.
            # Any previous segment is no longer reachable from the
            # manifest and can therefore be reclaimed.
            self.cleanup_unreferenced_segments(
                shard.shard_id,
                active_segments=manifest.active_segments,
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

        After the published generation has been loaded and validated,
        remove any stale segments left behind by previous generations
        or interrupted cleanup.
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
            shard.vector_index.clear()

            segments_dir = self.segments_directory(
                shard.shard_id
            )

            for segment_id in manifest.active_segments:
                segment = IndexSegment(
                    segment_id=segment_id,
                    path=segments_dir / f"{segment_id}.json",
                )

                if not segment.path.is_file():
                    raise FileNotFoundError(
                        segment.path
                    )

                snapshot = self.reader.read_snapshot(
                    segment
                )

                self._merge_index(
                    target=shard.index,
                    source=snapshot.index,
                )

                self._merge_vectors(
                    target=shard.vector_index,
                    source=snapshot.vector_index,
                )

            self._validate_vector_ownership(
                shard
            )

            if (
                shard.document_count
                != manifest.document_count
            ):
                raise ValueError(
                    f"Shard {shard.shard_id} document count "
                    "does not match its manifest."
                )

            # The shard has been successfully reconstructed from the
            # published manifest. Only now is it safe to remove stale
            # generations left on disk.
            self.cleanup_unreferenced_segments(
                shard.shard_id,
                active_segments=manifest.active_segments,
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

    def cleanup_unreferenced_segments(
        self,
        shard_id: str,
        active_segments: tuple[str, ...] | list[str] | None = None,
    ) -> list[str]:
        """
        Delete segment files that are not referenced by the published
        manifest.

        If active_segments is omitted, the current manifest is read.

        Returns:
            Segment IDs that were successfully deleted.

        This method is intentionally best-effort. Failure to delete an
        obsolete segment must not invalidate the already-published
        manifest or current shard generation.
        """
        if not self.exists(shard_id):
            return []

        if active_segments is None:
            active_segments = self.read_manifest(
                shard_id
            ).active_segments

        active = set(active_segments)
        segments_dir = self.segments_directory(
            shard_id
        )

        if not segments_dir.is_dir():
            return []

        deleted: list[str] = []

        for path in segments_dir.iterdir():
            if not path.is_file():
                continue

            if path.suffix != self.SEGMENT_SUFFIX:
                continue

            segment_id = path.stem

            if segment_id in active:
                continue

            try:
                path.unlink()
            except OSError:
                # Cleanup is housekeeping. The manifest has already
                # established the authoritative state, so an inability
                # to delete an obsolete file must not fail the shard.
                continue

            deleted.append(segment_id)

        return sorted(deleted)

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
                os.fsync(
                    file.fileno()
                )

            os.replace(
                temp_name,
                path,
            )

        finally:
            if os.path.exists(
                temp_name
            ):
                os.unlink(
                    temp_name
                )

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
            for posting in source.get_postings(
                term
            ):
                target.set_posting(
                    term,
                    Posting(
                        doc_id=posting.doc_id,
                        term_frequency=(
                            posting.term_frequency
                        ),
                        positions=list(
                            posting.positions
                        ),
                    ),
                )

    @staticmethod
    def _merge_vectors(
        target,
        source,
    ) -> None:
        for doc_id in sorted(
            source.document_ids
        ):
            embedding = source.get_embedding(
                doc_id
            )

            assert embedding is not None

            target.add_document(
                doc_id,
                embedding,
            )

    @staticmethod
    def _validate_vector_ownership(
        shard: Shard,
    ) -> None:
        lexical_ids = (
            shard.index.document_ids
        )

        vector_ids = (
            shard.vector_index.document_ids
        )

        orphaned = (
            vector_ids - lexical_ids
        )

        if orphaned:
            raise ValueError(
                "Persisted vector index contains documents "
                "that are not owned by shard "
                f"{shard.shard_id!r}: {sorted(orphaned)}"
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