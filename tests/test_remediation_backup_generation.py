"""Exercise retained journals through a real second transaction generation."""
import tempfile
import unittest
from pathlib import Path

from tools.bundle_transaction import (
    file_digest, prepare_transaction, publish_transaction, recover_transaction,
)


class RemediationBackupGenerationTest(unittest.TestCase):
    """A second generation preserves the first journal and restores current originals."""

    def test_second_generation_retains_original_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_journal = root / ".gate-staging/activation-backup/transaction.json"
            original_journal.parent.mkdir(parents=True)
            original_journal.write_text('{"state":"complete"}', encoding="utf-8")
            original_digest = file_digest(original_journal)
            target = root / "artifact.txt"
            target.write_text("current verified bytes", encoding="utf-8")
            source = root / "candidate.txt"
            source.write_text("approved replacement bytes", encoding="utf-8")
            sources = {"artifact.txt": source}
            files = {"artifact.txt": file_digest(source)}
            with self.assertRaises(ValueError):
                prepare_transaction(root, sources, files)
            backup_relative = ".gate-staging/remediation-backup"
            transaction = prepare_transaction(root, sources, files, backup_relative=backup_relative)
            publish_transaction(root, transaction, backup_relative=backup_relative)
            self.assertEqual(target.read_text(), "approved replacement bytes")
            self.assertEqual(file_digest(original_journal), original_digest)
            recover_transaction(root, transaction, backup_relative=backup_relative)
            self.assertEqual(target.read_text(), "current verified bytes")
            self.assertEqual(file_digest(original_journal), original_digest)


if __name__ == "__main__":
    unittest.main()
