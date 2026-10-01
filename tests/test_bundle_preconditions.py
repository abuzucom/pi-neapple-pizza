"""Exercise manifest validation and durable adoption recovery."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.adopt_agents_bundle import read_record, prepare_transaction, publish_transaction, recover_transaction


class BundlePreconditionsTest(unittest.TestCase):
    """Reject malformed manifests before any artifact access."""

    def test_invalid_record_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            path.write_bytes(b"[]")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                read_record(path, digest)

    def test_unapproved_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            path.write_bytes(b"{}")
            with self.assertRaises(ValueError):
                read_record(path, hashlib.sha256(b"different").hexdigest())

    def test_interrupted_publication_restores_original_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            candidate.mkdir()
            target = root / "artifact.txt"
            target.write_bytes(b"original")
            source = candidate / "artifact.txt"
            source.write_bytes(b"approved")
            files = {"artifact.txt": hashlib.sha256(b"approved").hexdigest()}
            transaction = prepare_transaction(root, {"artifact.txt": source}, files)
            publish_transaction(root, transaction)
            self.assertEqual(target.read_bytes(), b"approved")
            recover_transaction(root, transaction)
            self.assertEqual(target.read_bytes(), b"original")

    def test_changed_source_cannot_publish(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "candidate.txt"
            source.write_bytes(b"approved")
            files = {"artifact.txt": hashlib.sha256(b"approved").hexdigest()}
            transaction = prepare_transaction(root, {"artifact.txt": source}, files)
            source.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                publish_transaction(root, transaction)
            self.assertFalse((root / "artifact.txt").exists())
