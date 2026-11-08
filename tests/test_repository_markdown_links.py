"""Repository link checker: examples inside fenced code blocks are not links; real links are still checked.

Exercises the repository's Markdown checker and public-file boundary without
depending on locally retained maintainer documents.
"""
import importlib.util
import tempfile
import os
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

from tests.support import ROOT

SCRIPT = ROOT / ".github" / "scripts" / "check_repository.py"
spec = importlib.util.spec_from_file_location("check_repository", SCRIPT)
check_repository = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_repository)
wiki_spec = importlib.util.spec_from_file_location("sync_wiki", ROOT / ".github/scripts/sync_wiki.py")
sync_wiki = importlib.util.module_from_spec(wiki_spec)
wiki_spec.loader.exec_module(sync_wiki)


class FencedCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "real.md").write_text("# existe\n", encoding="utf-8")

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def links(self, name, text):
        return check_repository.markdown_links(self.write(name, text), self.root)

    def test_markdown_example_in_a_backtick_fence_is_ignored(self):
        errors, count = self.links("a.md", "Intro\n\n```markdown\n- [Phase](AAAA-MM-JJ-SUJET/00-PHASE.md)\n"
                                           "<a href=\"B01-OBJECTIF/00-BOUCLE.md\">x</a>\n```\n")
        self.assertEqual(errors, [])
        self.assertEqual(count, 0)

    def test_tilde_fence_closes_consistently_and_text_after_it_is_still_checked(self):
        text = ("~~~\n[exemple](80-SYNTHESE.md)\n~~~~ not a closing fence (trailing text)\n"
                "[toujours exemple](90-BILAN.md)\n~~~\n[vrai lien absent](02-CODEX-MISSION-CLAUDE.md)\n")
        errors, count = self.links("b.md", text)
        self.assertEqual(count, 1)
        self.assertEqual(errors, ["b.md: missing 02-CODEX-MISSION-CLAUDE.md"])
        # A longer closing fence of the same character also closes the block.
        errors, count = self.links("c.md", "````\n[x](absent.md)\n`````\n[ok](real.md)\n")
        self.assertEqual((errors, count), ([], 1))
        # A fence of the other character does not close the block (still ignored, up to the end).
        errors, count = self.links("d.md", "```\n[x](absent.md)\n~~~\n[y](absent-aussi.md)\n")
        self.assertEqual((errors, count), ([], 0))

    def test_real_existing_link_outside_a_block_is_accepted(self):
        errors, count = self.links("e.md", "[voir](real.md) et [ancre](real.md#titre)\n")
        self.assertEqual((errors, count), ([], 2))

    def test_real_missing_link_outside_a_block_is_still_detected_next_to_an_example_block(self):
        text = "```\n[exemple](AAAA-MM-JJ-SUJET/00-PHASE.md)\n```\n\n[cassé](nulle-part.md) et [bon](real.md)\n"
        errors, count = self.links("f.md", text)
        self.assertEqual(errors, ["f.md: missing nulle-part.md"])
        self.assertEqual(count, 2)

    def test_strip_keeps_line_count_and_outside_text(self):
        text = "un\n```\ndeux\n```\ntrois\n"
        stripped = check_repository.strip_fenced_code(text)
        self.assertEqual(stripped.count("\n"), text.count("\n"))
        self.assertEqual(stripped, "un\n\n\n\ntrois\n")


class PublishedDocumentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_five_fenced_examples_need_no_real_files(self):
        examples = ("examples/guide.md", "examples/settings.md", "sample/README.md",
                    "tutorials/download.md", "templates/report.md")
        path = self.root / "README.md"
        path.write_text("```markdown\n" + "\n".join(f"[Example]({p})" for p in examples) + "\n```\n", encoding="utf-8")
        self.assertEqual(check_repository.markdown_links(path, self.root), ([], 0))
        self.assertEqual(check_repository.check(ROOT)["errors"], [])

    def test_existing_local_only_target_is_rejected(self):
        path = self.root / "README.md"
        local = self.root / "private-notes.md"
        path.write_text("[Instructions](private-notes.md)\n", encoding="utf-8")
        local.write_text("Local instructions\n", encoding="utf-8")
        selected = {Path(os.path.abspath(path))}
        self.assertEqual(check_repository.markdown_links(path, self.root, published_paths=selected),
                         (["README.md: unpublished target private-notes.md"], 1))
        selected.add(Path(os.path.abspath(local)))
        self.assertEqual(check_repository.markdown_links(path, self.root, published_paths=selected), ([], 1))

    def test_default_ignore_and_force_added_document_are_detected(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        (self.root / ".gitignore").write_text((ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")
        (self.root / "docs").mkdir()
        private = self.root / "docs" / "new-internal-notes.md"
        private.write_text("Local only\n", encoding="utf-8")
        ignored = subprocess.run(["git", "check-ignore", "docs/new-internal-notes.md"], cwd=self.root, capture_output=True)
        self.assertEqual(ignored.returncode, 0)
        subprocess.run(["git", "add", "--force", "docs/new-internal-notes.md"], cwd=self.root, check=True)
        self.assertEqual(check_repository.publication_errors(self.root, ["docs/new-internal-notes.md"]),
                         ["Excluded file in public selection: docs/new-internal-notes.md"])
        self.assertEqual(check_repository.publication_errors(self.root, ["README.md"]), [])
        for name in ("install-local.command", ".macos-local-install.json"):
            (self.root / name).write_text("Local installation helper\n", encoding="utf-8")
            ignored = subprocess.run(["git", "check-ignore", name], cwd=self.root, capture_output=True)
            self.assertEqual(ignored.returncode, 0, name)
            subprocess.run(["git", "add", "--force", name], cwd=self.root, check=True)
            self.assertEqual(check_repository.publication_errors(self.root, [name]),
                             ["Excluded file in public selection: " + name])

    def test_wiki_selection_preserves_local_only_notes(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        (self.root / ".gitignore").write_text((ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")
        wiki = self.root / "docs/wiki"
        wiki.mkdir(parents=True)
        home, private = wiki / "Home.md", wiki / "private-notes.md"
        home.write_text("# Public help\n", encoding="utf-8")
        private.write_text("Private working notes\n", encoding="utf-8")
        subprocess.run(["git", "add", "docs/wiki/Home.md"], cwd=self.root, check=True)
        with patch.object(sync_wiki, "ROOT", self.root):
            self.assertEqual(sync_wiki.reviewed_sources(), [home])
            subprocess.run(["git", "add", "--force", "docs/wiki/private-notes.md"], cwd=self.root, check=True)
            with self.assertRaisesRegex(ValueError, "excluded files"):
                sync_wiki.reviewed_sources()
        self.assertEqual(private.read_text(encoding="utf-8"), "Private working notes\n")


if __name__ == "__main__":
    unittest.main()
