import json
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.sh"


class BootstrapInstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.temp.name)
        self.env = os.environ.copy()
        self.env.update({
            "HOME": str(base / "home"),
            "CLAUDE_CONFIG_DIR": str(base / "claude"),
            "CODEX_HOME": str(base / "codex"),
            "XDG_CONFIG_HOME": str(base / "config"),
            "GIT_CONFIG_GLOBAL": str(base / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
        })
        pathlib.Path(self.env["HOME"]).mkdir()
        self.repo = base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True, env=self.env)

    def tearDown(self):
        self.temp.cleanup()

    def run_bootstrap(self, *args, expect=0, env=None):
        result = subprocess.run([str(BOOTSTRAP), *args], env=env or self.env, text=True, capture_output=True)
        self.assertEqual(expect, result.returncode, result.stderr)
        return result

    def hermetic_path_without_npx(self, extra_dir=None):
        # Build a PATH that resolves only the interpreters bootstrap.sh
        # itself needs (env, bash, python3, git) plus anything the caller
        # supplies, and nothing else — so the test cannot pick up a real
        # `npx` from the ambient system PATH.
        bin_dir = pathlib.Path(tempfile.mkdtemp(dir=self.temp.name))
        for name in ("env", "bash", "dirname", "python3", "git"):
            found = shutil.which(name)
            if found:
                (bin_dir / name).symlink_to(found)
        return f"{extra_dir}:{bin_dir}" if extra_dir else str(bin_dir)

    def snapshot(self, root):
        result = {}
        root = pathlib.Path(root)
        if not root.exists():
            return result
        for path in sorted(root.rglob("*")):
            relative = str(path.relative_to(root))
            if path.is_symlink():
                result[relative] = ("symlink", os.readlink(path), stat.S_IMODE(path.lstat().st_mode))
            elif path.is_file():
                result[relative] = ("file", path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        return result

    def test_default_provider_installs_both(self):
        self.run_bootstrap()
        self.assertTrue(pathlib.Path(self.env["CLAUDE_CONFIG_DIR"], "CLAUDE.md").exists())
        self.assertTrue(pathlib.Path(self.env["CODEX_HOME"], "config.toml").exists())

    def test_claude_provider_is_scoped(self):
        self.run_bootstrap("--provider", "claude")
        self.assertTrue(pathlib.Path(self.env["CLAUDE_CONFIG_DIR"], "settings.json").exists())
        self.assertFalse(pathlib.Path(self.env["CODEX_HOME"]).exists())

    def test_codex_provider_is_scoped(self):
        self.run_bootstrap("--provider", "codex")
        self.assertTrue(pathlib.Path(self.env["CODEX_HOME"], "hooks.json").exists())
        self.assertFalse(pathlib.Path(self.env["CLAUDE_CONFIG_DIR"]).exists())

    def test_dry_run_has_no_side_effects(self):
        result = self.run_bootstrap("--dry-run")
        self.assertIn("Planned operations:", result.stdout)
        self.assertFalse(pathlib.Path(self.env["CLAUDE_CONFIG_DIR"]).exists())
        self.assertFalse(pathlib.Path(self.env["CODEX_HOME"]).exists())

    def test_claude_json_merge_preserves_foreign_values(self):
        path = pathlib.Path(self.env["CLAUDE_CONFIG_DIR"])
        path.mkdir()
        settings = path / "settings.json"
        settings.write_text(json.dumps({"model": "private", "foreign": {"keep": True}, "hooks": {"Foreign": [{"x": 1}]}}))
        self.run_bootstrap("--provider", "claude")
        actual = json.loads(settings.read_text())
        self.assertEqual("private", actual["model"])
        self.assertEqual({"keep": True}, actual["foreign"])
        self.assertIn("Foreign", actual["hooks"])
        self.assertIn("SessionStart", actual["hooks"])

    def test_claude_block_preserves_foreign_bytes(self):
        path = pathlib.Path(self.env["CLAUDE_CONFIG_DIR"])
        path.mkdir()
        target = path / "CLAUDE.md"
        target.write_text("before\n<!-- OMC:START -->\nomc\n<!-- OMC:END -->\nafter\n")
        self.run_bootstrap("--provider", "claude")
        content = target.read_text()
        self.assertIn("before\n", content)
        self.assertIn("<!-- OMC:START -->\nomc\n<!-- OMC:END -->", content)
        self.assertIn(str(path / "skills-hub/AGENTS.base.md"), content)

    def test_ambiguous_claude_block_refuses(self):
        path = pathlib.Path(self.env["CLAUDE_CONFIG_DIR"])
        path.mkdir()
        (path / "CLAUDE.md").write_text("<!-- SKILLS-HUB:START -->\none\n<!-- SKILLS-HUB:END -->\n<!-- SKILLS-HUB:START -->\ntwo\n<!-- SKILLS-HUB:END -->")
        self.run_bootstrap("--provider", "claude", expect=1)

    def test_codex_agents_is_absolute_symlink(self):
        self.run_bootstrap("--provider", "codex")
        target = pathlib.Path(self.env["CODEX_HOME"], "AGENTS.md")
        self.assertTrue(target.is_symlink())
        self.assertTrue(os.path.isabs(os.readlink(target)))

    def test_codex_foreign_agents_is_backed_up(self):
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "AGENTS.md"
        target.write_text("foreign")
        self.run_bootstrap("--provider", "codex")
        self.assertTrue(target.is_symlink())
        self.assertTrue(list(path.glob("AGENTS.md.bak.*")))

    def test_codex_json_handlers_are_additive(self):
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "hooks.json"
        target.write_text(json.dumps({"Foreign": [{"hooks": [{"type": "command", "command": "private"}]}]}))
        self.run_bootstrap("--provider", "codex")
        actual = json.loads(target.read_text())
        self.assertIn("Foreign", actual)
        self.assertIn("SessionStart", actual["hooks"])

    def test_codex_toml_preserves_omc_bytes(self):
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "config.toml"
        omc = "# BEGIN OMC MANAGED MCP REGISTRY\n[omc]\nvalue = \"x\"\n# END OMC MANAGED MCP REGISTRY\n"
        target.write_text(omc + "\nprivate = true\n")
        self.run_bootstrap("--provider", "codex")
        actual = target.read_text()
        self.assertIn(omc, actual)
        self.assertIn("private = true", actual)

    def test_malformed_toml_refuses_before_changes(self):
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        (path / "config.toml").write_text("broken = [")
        self.run_bootstrap("--provider", "codex", expect=1)
        self.assertFalse((path / "hooks.json").exists())

    def test_agent_definitions_are_installed(self):
        self.run_bootstrap("--provider", "codex")
        self.assertEqual(3, len(list(pathlib.Path(self.env["CODEX_HOME"], "agents").glob("*.toml"))))

    def test_hooks_keep_executable_mode(self):
        self.run_bootstrap("--provider", "claude")
        mode = pathlib.Path(self.env["CLAUDE_CONFIG_DIR"], "hooks/completion-gate.sh").stat().st_mode
        self.assertTrue(mode & 0o100)

    def test_global_hooks_path_is_set(self):
        self.run_bootstrap("--provider", "claude")
        value = subprocess.check_output(["git", "config", "--global", "--get", "core.hooksPath"], env=self.env, text=True).strip()
        self.assertEqual(str(pathlib.Path(self.env["XDG_CONFIG_HOME"], "git/skills-hub-hooks")), value)

    def test_foreign_global_hooks_path_is_refused(self):
        subprocess.run(["git", "config", "--global", "core.hooksPath", "/private/hooks"], env=self.env, check=True)
        self.run_bootstrap("--provider", "claude", expect=1)

    def test_overlay_wins_without_copying_into_checkout(self):
        overlay = pathlib.Path(self.temp.name, "overlay")
        (overlay / "shared").mkdir(parents=True)
        (overlay / "shared/AGENTS.base.md").write_text("overlay base\n")
        self.run_bootstrap("--provider", "codex", "--overlay", str(overlay))
        self.assertEqual("overlay base\n", pathlib.Path(self.env["CODEX_HOME"], "AGENTS.md").resolve().read_text())
        self.assertFalse((ROOT / "shared").exists())

    def test_partial_overlay_retains_public_files(self):
        overlay = pathlib.Path(self.temp.name, "overlay")
        (overlay / "shared/hooks").mkdir(parents=True)
        (overlay / "shared/hooks/completion-gate.sh").write_text("overlay hook\n")
        self.run_bootstrap("--provider", "claude", "--overlay", str(overlay))
        config = pathlib.Path(self.env["CLAUDE_CONFIG_DIR"])
        self.assertEqual("overlay hook\n", (config / "hooks/completion-gate.sh").read_text())
        self.assertTrue((config / "hooks/sessionstart-repo-context.sh").exists())

    def test_partial_agent_overlay_retains_public_agents(self):
        overlay = pathlib.Path(self.temp.name, "overlay")
        (overlay / "codex/agents").mkdir(parents=True)
        (overlay / "codex/agents/reviewer.toml").write_text("overlay reviewer\n")
        self.run_bootstrap("--provider", "codex", "--overlay", str(overlay))
        agents = pathlib.Path(self.env["CODEX_HOME"], "agents")
        self.assertEqual("overlay reviewer\n", (agents / "reviewer.toml").read_text())
        self.assertTrue((agents / "explorer.toml").exists())

    def test_second_run_is_byte_and_backup_set_idempotent(self):
        self.run_bootstrap("--provider", "claude")
        before = self.snapshot(self.temp.name)
        before_backups = sorted(str(path) for path in pathlib.Path(self.temp.name).rglob("*.bak.*"))
        self.run_bootstrap("--provider", "claude")
        self.assertEqual(before, self.snapshot(self.temp.name))
        self.assertEqual(before_backups, sorted(str(path) for path in pathlib.Path(self.temp.name).rglob("*.bak.*")))

    def test_codex_second_run_does_not_rewrite_config_or_create_backup(self):
        self.run_bootstrap("--provider", "codex")
        before = self.snapshot(self.temp.name)
        before_backups = sorted(str(path) for path in pathlib.Path(self.temp.name).rglob("*.bak.*"))
        self.run_bootstrap("--provider", "codex")
        self.assertEqual(before, self.snapshot(self.temp.name))
        self.assertEqual(before_backups, sorted(str(path) for path in pathlib.Path(self.temp.name).rglob("*.bak.*")))

    def test_rollback_removes_partial_state(self):
        env = self.env.copy()
        env["BOOTSTRAP_TEST_FAIL_AFTER"] = "2"
        self.run_bootstrap("--provider", "claude", expect=1, env=env)
        self.assertFalse(pathlib.Path(self.env["CLAUDE_CONFIG_DIR"]).exists())

    def test_missing_npx_is_nonfatal(self):
        env = self.env.copy()
        env["PATH"] = self.hermetic_path_without_npx()
        self.run_bootstrap("--provider", "claude", "--install-skills", env=env)

    def test_failing_npx_prints_warning_but_keeps_installed_files(self):
        bin_dir = pathlib.Path(self.temp.name, "bin")
        bin_dir.mkdir()
        npx = bin_dir / "npx"
        npx.write_text("#!/bin/sh\nexit 7\n")
        npx.chmod(0o755)
        env = self.env.copy()
        env["PATH"] = self.hermetic_path_without_npx(extra_dir=str(bin_dir))
        result = self.run_bootstrap("--provider", "claude", "--install-skills", env=env)
        self.assertIn("Warning: official skills installation failed", result.stderr)
        self.assertTrue(pathlib.Path(self.env["CLAUDE_CONFIG_DIR"]).exists())
        self.assertTrue(pathlib.Path(self.env["XDG_CONFIG_HOME"], "git").exists())

    def test_codex_prints_hooks_approval_instruction(self):
        result = self.run_bootstrap("--provider", "codex")
        self.assertIn("/hooks", result.stdout)

    def test_markdown_without_block_appends_only_managed_block(self):
        path = pathlib.Path(self.env["CLAUDE_CONFIG_DIR"])
        path.mkdir()
        target = path / "CLAUDE.md"
        target.write_text("private\n")
        self.run_bootstrap("--provider", "claude")
        self.assertTrue(target.read_text().startswith("private\n"))
        self.assertEqual(1, target.read_text().count("SKILLS-HUB:START"))

    def test_codex_toml_rejects_legacy_keys_in_existing_section(self):
        """Test that merge_toml refuses to merge when existing section has unknown keys."""
        import tomllib
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "config.toml"
        # Legacy config with keys not in template (max_threads is legacy, not in template)
        legacy = """[agents]
max_threads = 6
max_depth = 1
"""
        target.write_text(legacy)
        # Without --force flag, should refuse
        result = self.run_bootstrap("--provider", "codex", expect=1)
        self.assertIn("unrecognized keys", result.stderr)
        self.assertIn("max_threads", result.stderr)
        # Original config should be unchanged
        self.assertEqual(legacy, target.read_text())

    def test_codex_toml_allows_legacy_keys_with_force_flag(self):
        """Test that --merge-unknown-keys flag allows merging despite unknown keys."""
        import tomllib
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "config.toml"
        legacy = """[agents]
max_threads = 6
max_depth = 1
"""
        target.write_text(legacy)
        # With --merge-unknown-keys flag, should succeed
        result = self.run_bootstrap("--provider", "codex", "--merge-unknown-keys")
        self.assertEqual(0, result.returncode)
        # Config should now have both legacy and new keys
        merged = target.read_text()
        parsed = tomllib.loads(merged)
        self.assertIn("agents", parsed)
        self.assertEqual(6, parsed["agents"]["max_threads"])
        self.assertEqual(1, parsed["agents"]["max_depth"])
        self.assertTrue(parsed["agents"]["enabled"])
        self.assertEqual(6, parsed["agents"]["max_concurrent_threads_per_session"])
        self.assertEqual("medium", parsed["agents"]["default_subagent_reasoning_effort"])

    def test_codex_toml_rejects_unknown_keys_in_features_section(self):
        """Test that unknown keys in [features] section are also caught."""
        import tomllib
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "config.toml"
        legacy = """[features]
custom_legacy_feature = true
hooks = true
"""
        target.write_text(legacy)
        result = self.run_bootstrap("--provider", "codex", expect=1)
        self.assertIn("unrecognized keys", result.stderr)
        self.assertIn("custom_legacy_feature", result.stderr)
        self.assertEqual(legacy, target.read_text())

    def test_codex_toml_multiple_unknown_keys_reported(self):
        """Test that all unknown keys are reported in error message."""
        import tomllib
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "config.toml"
        legacy = """[agents]
legacy_key1 = "value1"
legacy_key2 = 42
enabled = false
"""
        target.write_text(legacy)
        result = self.run_bootstrap("--provider", "codex", expect=1)
        self.assertIn("unrecognized keys", result.stderr)
        self.assertIn("legacy_key1", result.stderr)
        self.assertIn("legacy_key2", result.stderr)
        self.assertEqual(legacy, target.read_text())

    def test_codex_toml_unknown_keys_in_multiple_sections(self):
        """Test that unknown keys in multiple sections are all caught (first one reported)."""
        import tomllib
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "config.toml"
        legacy = """[agents]
legacy_agent_key = 1
[features]
legacy_feature_key = true
"""
        target.write_text(legacy)
        result = self.run_bootstrap("--provider", "codex", expect=1)
        self.assertIn("unrecognized keys", result.stderr)
        # The implementation reports the first section with unknown keys it encounters
        # (order depends on template iteration, which is deterministic)
        self.assertIn("legacy_feature_key", result.stderr)
        self.assertEqual(legacy, target.read_text())

    def test_codex_toml_subtable_keys_not_confused(self):
        """Test that keys in subtables like [agents.explorer] are not treated as unknown in parent."""
        import tomllib
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "config.toml"
        # This mimics a config with subtable keys - these should be fine
        legacy = """[agents]
enabled = true
max_concurrent_threads_per_session = 4

[agents.explorer]
description = "custom explorer"
config_file = "agents/explorer.toml"
"""
        target.write_text(legacy)
        result = self.run_bootstrap("--provider", "codex")
        self.assertEqual(0, result.returncode)
        merged = target.read_text()
        parsed = tomllib.loads(merged)
        self.assertIn("agents", parsed)
        self.assertTrue(parsed["agents"]["enabled"])
        self.assertEqual(4, parsed["agents"]["max_concurrent_threads_per_session"])
        self.assertIn("explorer", parsed["agents"])
        self.assertEqual("custom explorer", parsed["agents"]["explorer"]["description"])

    def test_codex_toml_migration_workflow(self):
        """Test the recommended migration workflow: copy legacy value, remove legacy key, re-run."""
        import tomllib
        path = pathlib.Path(self.env["CODEX_HOME"])
        path.mkdir()
        target = path / "config.toml"
        
        # Step 1: User has legacy config
        legacy = """[agents]
max_threads = 8
max_depth = 2
"""
        target.write_text(legacy)
        result = self.run_bootstrap("--provider", "codex", expect=1)
        self.assertIn("unrecognized keys", result.stderr)
        
        # Step 2: User migrates - copies value to new key, removes legacy key
        migrated = """[agents]
max_concurrent_threads_per_session = 8
max_depth = 2
"""
        target.write_text(migrated)
        
        # Step 3: Bootstrap should now succeed
        result = self.run_bootstrap("--provider", "codex")
        self.assertEqual(0, result.returncode)
        
        merged = target.read_text()
        parsed = tomllib.loads(merged)
        self.assertEqual(8, parsed["agents"]["max_concurrent_threads_per_session"])
        self.assertEqual(2, parsed["agents"]["max_depth"])
        self.assertTrue(parsed["agents"]["enabled"])
        # Legacy key should not be present
        self.assertNotIn("max_threads", parsed["agents"])


if __name__ == "__main__":
    unittest.main()