"""Merged annotation restoration must fix the repeated-first-method queue."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from fingerprint_atlas.methods import get_method, seed_methods, update_method
from fingerprint_atlas.methods_cli import (
    SECTIONS, _render_edit_file, cmd_queue_next, cmd_restore_merged_drafts,
)


class MergedMethodRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = str(self.root / "methods.db")
        self.drafts = self.root / "methods_drafts"
        seed_methods(self.db)

    def annotation(self, run, name="chiarella_iori", **values):
        method = get_method(self.db, name)
        for section in SECTIONS:
            setattr(method, section, values.get(section, ""))
        path = self.drafts / str(run) / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render_edit_file(method), encoding="utf-8")
        return path

    def restore(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return cmd_restore_merged_drafts(self.db, str(self.drafts))

    def next_method(self):
        output = io.StringIO()
        with redirect_stdout(output):
            cmd_queue_next(self.db, 1)
        return output.getvalue().strip()

    def test_restores_all_fields_and_advances_first_method_without_editing_file(self):
        values = {section: f"reviewed {section}\nsecond line" for section in SECTIONS}
        path = self.annotation(123, **values)
        before = path.read_bytes()
        self.assertEqual(self.next_method(), "chiarella_iori")
        self.assertEqual(self.restore(), 0)
        method = get_method(self.db, "chiarella_iori")
        self.assertEqual({section: getattr(method, section) for section in SECTIONS}, values)
        self.assertEqual(self.next_method(), "cont_bouchaud")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.restore(), 0)

    def test_latest_run_is_numeric_and_preserves_both_source_files(self):
        old = self.annotation(9, novelty_notes="old")
        new = self.annotation(10, novelty_notes="new")
        self.assertEqual(self.restore(), 0)
        self.assertEqual(get_method(self.db, "chiarella_iori").novelty_notes, "new")
        self.assertTrue(old.exists() and new.exists())

    def test_file_existence_and_empty_sections_do_not_count_as_annotation(self):
        self.annotation(123)
        self.assertEqual(self.restore(), 0)
        self.assertEqual(self.next_method(), "chiarella_iori")

    def test_malformed_selected_draft_is_rejected_before_any_db_write(self):
        self.annotation(123, novelty_notes="must not partially import")
        broken = self.annotation(123, name="cont_bouchaud", novelty_notes="x")
        broken.write_text("# methodology notes for: cont_bouchaud\n## novelty_notes\nx\n", encoding="utf-8")
        self.assertEqual(self.restore(), 1)
        self.assertEqual(get_method(self.db, "chiarella_iori").novelty_notes, "")

    def test_mismatched_header_is_rejected(self):
        path = self.annotation(123, novelty_notes="x")
        path.write_text(path.read_text().replace("notes for: chiarella_iori", "notes for: cont_bouchaud"), encoding="utf-8")
        self.assertEqual(self.restore(), 1)
        self.assertEqual(self.next_method(), "chiarella_iori")

    def test_existing_db_commentary_is_not_replaced(self):
        self.annotation(123, novelty_notes="merged older note")
        update_method(self.db, "chiarella_iori", novelty_notes="local reviewed update")
        self.assertEqual(self.restore(), 1)
        self.assertEqual(get_method(self.db, "chiarella_iori").novelty_notes, "local reviewed update")


if __name__ == "__main__":
    unittest.main()
