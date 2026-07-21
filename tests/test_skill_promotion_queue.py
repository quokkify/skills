from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPOSITORY_ROOT
    / "skills"
    / "skill-management"
    / "skill-promotion-queue"
    / "scripts"
    / "publish_queue.py"
)
SPEC = importlib.util.spec_from_file_location("publish_queue", SCRIPT)
assert SPEC and SPEC.loader
publish_queue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish_queue)


class SkillPromotionQueueTests(unittest.TestCase):
    def test_accepts_public_skill_and_support_paths(self) -> None:
        accepted = [
            "skills/repository/example/SKILL.md",
            "skills/repository/example/scripts/check.py",
            "docs/skill-catalog.md",
            "tests/test_example.py",
            "scripts/validate_repo.py",
            "adapters/codex/AGENTS.md",
            "README.md",
            "SECURITY.md",
            "THIRD_PARTY_NOTICES.md",
        ]
        for path in accepted:
            with self.subTest(path=path):
                self.assertTrue(publish_queue.path_is_allowed(path))

    def test_rejects_runtime_state_release_and_workflow_paths(self) -> None:
        rejected = [
            ".env",
            ".github/workflows/publish.yml",
            "CHANGELOG.md",
            "release-please-config.json",
            "skills/example/.secrets/token",
            "skills/example/transcripts/session.md",
            "skills/example/MEMORY.md",
            "../outside.md",
            "/absolute/path.md",
        ]
        for path in rejected:
            with self.subTest(path=path):
                self.assertFalse(publish_queue.path_is_allowed(path))

    def test_lane_is_bounded_and_branch_is_deterministic(self) -> None:
        self.assertEqual(
            publish_queue.validate_lane("local-laptop"),
            "automation/skill-improvements/local-laptop",
        )
        for lane in ["", "Uppercase", "has space", "slash/name", "x" * 64]:
            with self.subTest(lane=lane):
                with self.assertRaises(publish_queue.QueueError):
                    publish_queue.validate_lane(lane)

    def test_repository_requires_owner_name_not_url(self) -> None:
        publish_queue.validate_repository("example/skills")
        for repository in ["skills", "https://github.com/example/skills", "../skills"]:
            with self.subTest(repository=repository):
                with self.assertRaises(publish_queue.QueueError):
                    publish_queue.validate_repository(repository)

    def test_empty_and_disallowed_diffs_fail_closed(self) -> None:
        with self.assertRaisesRegex(publish_queue.QueueError, "no changed paths"):
            publish_queue.ensure_public_paths([])
        with self.assertRaisesRegex(publish_queue.QueueError, "disallowed paths"):
            publish_queue.ensure_public_paths(["skills/example/SKILL.md", ".env"])

    def test_pull_request_response_requires_json_array_of_objects(self) -> None:
        self.assertEqual(publish_queue.parse_pull_requests("[]"), [])
        with self.assertRaises(publish_queue.QueueError):
            publish_queue.parse_pull_requests("not-json")
        with self.assertRaises(publish_queue.QueueError):
            publish_queue.parse_pull_requests('{}')
        with self.assertRaises(publish_queue.QueueError):
            publish_queue.parse_pull_requests('["bad"]')

    def test_body_records_deferred_review_without_authorizing_merge(self) -> None:
        body = publish_queue.build_body(
            lane="test-lane",
            head="a" * 40,
            commits=["feat(skills): improve example"],
            paths=["skills/repository/example/SKILL.md"],
        )
        self.assertIn("Independent review is intentionally deferred", body)
        self.assertIn("never merges", body)
        self.assertIn("test-lane", body)
        self.assertIn("skills/repository/example/SKILL.md", body)


if __name__ == "__main__":
    unittest.main()
