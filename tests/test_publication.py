import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "indexer", Path(__file__).resolve().parents[1] / "update-database.py"
)
indexer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indexer)

MARKDOWN = (
    "\n# A public section\n\n"
    "This intentionally synthetic paragraph contains enough ordinary text "
    "to produce an entry in the searchable documentation index.\n"
)


class PublicIndexTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.blog = {
            "type": "blog",
            "path": "blog",
            "url": "https://blogs.comphy-lab.org",
            "repo_url": "unused",
        }
        self.env = patch.dict(os.environ, {"GITHUB_WORKSPACE": tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.blog_dir = self.root / "blog"
        self.blog_dir.mkdir()

    def write(self, name, frontmatter, body=MARKDOWN):
        file = self.blog_dir / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(frontmatter + body, encoding="utf-8")
        return file

    def test_repository_indexes_only_explicitly_public_vault_pages(self):
        self.write("Blog/published-page.md", "---\npublish: true # Public\n---\n")
        self.write("Blog/opted-out.md", "---\npublish: false\n---\n")
        self.write("Blog/implicit-page.md", "")
        self.write("docs/internal-page.md", "---\npublish: true\n---\n")
        self.write("_scripts/scripting-page.md", "---\npublish: true\n---\n")
        self.write("_AtomicNotes/public-atom.md", "---\npublish: true\n---\n")
        found = []
        with (
            patch.object(indexer, "clone_or_update_repo", return_value=True),
            patch.object(indexer, "cleanup_repo"),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            indexer.process_repository(self.blog, found)
        self.assertTrue(found)
        urls = {entry["url"].split("#", 1)[0] for entry in found}
        self.assertEqual(urls, {
            "https://blogs.comphy-lab.org/Blog/published-page/",
            "https://blogs.comphy-lab.org/_AtomicNotes/public-atom/",
        })
        self.assertNotIn("opted-out", out.getvalue())

    def test_publication_flag_requires_unambiguous_boolean(self):
        valid = ["publish: true", '"publish": true', "title: Example\npublish: true"]
        invalid = [
            "publish: false", "publish: 'true'", "publish: yes",
            "nested:\n  publish: true", "publish: true\npublish: false",
            "publish: true\npublish: true", "publish: [true]", "publish: {",
        ]
        for flag in valid:
            with self.subTest(flag=flag):
                self.assertTrue(indexer.has_explicit_quartz_publish(f"---\n{flag}\n---\n"))
        for flag in invalid:
            with self.subTest(flag=flag):
                self.assertFalse(indexer.has_explicit_quartz_publish(f"---\n{flag}\n---\n"))

    def test_repository_input_requires_regular_file_and_parents(self):
        regular = self.write("Blog/sample.md", "---\npublish: true\n---\n")
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "local-fixture.md").write_text("synthetic fixture", encoding="utf-8")
        link = self.blog_dir / "Blog/linked.md"
        link.symlink_to(regular)
        alias = self.blog_dir / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        root_alias = self.root / "alias-root"
        root_alias.symlink_to(self.blog_dir, target_is_directory=True)
        self.assertTrue(indexer.is_regular_repository_input(self.blog_dir, regular))
        for file in (link, alias / "local-fixture.md", self.blog_dir / ".hidden.md"):
            with self.subTest(file=file):
                self.assertFalse(indexer.is_regular_repository_input(self.blog_dir, file))
        self.assertFalse(indexer.is_regular_repository_input(root_alias, root_alias / "Blog/sample.md"))

    def test_markdown_and_html_handlers_share_the_input_gate(self):
        blocked = self.blog_dir / ".hidden.html"
        with patch.object(Path, "read_text", side_effect=AssertionError("unexpected read")):
            for handler in (
                indexer.process_markdown_file, indexer.process_html_file, indexer.process_docs_html_file
            ):
                found = []
                handler(self.blog, blocked, found)
                self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
