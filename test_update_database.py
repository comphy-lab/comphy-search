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


if __name__ == "__main__":
    unittest.main()
