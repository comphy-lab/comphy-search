import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("update-database.py")
SPEC = importlib.util.spec_from_file_location("update_database", MODULE_PATH)
UPDATE_DATABASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE_DATABASE)


class PrivacyFilterTests(unittest.TestCase):
    def test_agent_control_files_are_not_search_content(self):
        self.assertTrue(
            UPDATE_DATABASE.should_exclude_file(Path("/repo/AGENTS.md"))
        )
        self.assertTrue(
            UPDATE_DATABASE.should_exclude_file(Path("/repo/CLAUDE.md"))
        )
        self.assertFalse(
            UPDATE_DATABASE.should_exclude_file(Path("/repo/Blog/research.md"))
        )

    def test_private_workflow_metadata_is_removed_from_public_blog_entries(self):
        entry = {
            "title": "Publishing guidance",
            "url": "https://blogs.comphy-lab.org/guidance/",
            "content": "Route private notes to the private Obsidian vault.",
        }
        self.assertTrue(
            UPDATE_DATABASE.is_internal_public_blog_entry(entry)
        )

    def test_legitimate_public_blog_content_remains_searchable(self):
        entry = {
            "title": "Drop impact",
            "url": "https://blogs.comphy-lab.org/blog/drop-impact/",
            "content": "A public research note on capillary dynamics.",
        }
        self.assertFalse(
            UPDATE_DATABASE.is_internal_public_blog_entry(entry)
        )


class DocsPriorityTests(unittest.TestCase):
    def test_docs_repos_share_blog_priority_band(self):
        """Project docs must not sit below blog under priority-first sort."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = Path(tmp) / "Viscoelastic3D"
            repo_dir.mkdir()
            index = repo_dir / "index.html"
            index.write_text("<html></html>")
            deep = repo_dir / "src" / "solver.c"
            deep.parent.mkdir()
            deep.write_text("int main(){}")

            repo_config = {
                "type": "docs",
                "path": "Viscoelastic3D",
                "url": "https://comphy-lab.org/Viscoelastic3D",
            }
            old_workspace = os.environ.get("GITHUB_WORKSPACE")
            os.environ["GITHUB_WORKSPACE"] = tmp
            try:
                self.assertEqual(
                    UPDATE_DATABASE.get_priority(repo_config, index), 3
                )
                self.assertEqual(
                    UPDATE_DATABASE.get_priority(repo_config, deep), 3
                )
            finally:
                if old_workspace is None:
                    os.environ.pop("GITHUB_WORKSPACE", None)
                else:
                    os.environ["GITHUB_WORKSPACE"] = old_workspace


if __name__ == "__main__":
    unittest.main()
