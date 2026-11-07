"""Repository link checker: examples inside fenced code blocks are not links; real links are still checked.

Exercises the exact functions ``.github/scripts/check_repository.py`` uses for
Markdown files (``strip_fenced_code`` and ``markdown_links``), plus the full
``check()`` on the real repository for the UNIVERSAL template examples (F3).
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT

SCRIPT = ROOT / ".github" / "scripts" / "check_repository.py"
spec = importlib.util.spec_from_file_location("check_repository", SCRIPT)
check_repository = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_repository)


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


class UniversalModelsTests(unittest.TestCase):
    EXAMPLES = ("AAAA-MM-JJ-SUJET/00-PHASE.md", "B01-OBJECTIF/00-BOUCLE.md", "80-SYNTHESE.md", "90-BILAN.md",
                "02-CODEX-MISSION-CLAUDE.md")

    def test_the_five_template_examples_are_ignored_by_the_checker_path(self):
        path = ROOT / "docs" / "UNIVERSAL" / "03-MODELES.md"
        text = path.read_text(encoding="utf-8")
        for example in self.EXAMPLES:
            self.assertIn(example, text)                     # the examples are still there, not deleted
        errors, _ = check_repository.markdown_links(path, ROOT)
        self.assertEqual([e for e in errors if any(x in e for x in self.EXAMPLES)], [])
        result = check_repository.check(ROOT)                 # the real run of the repository checker
        self.assertEqual([e for e in result["errors"] if "03-MODELES" in e], [])


if __name__ == "__main__":
    unittest.main()
