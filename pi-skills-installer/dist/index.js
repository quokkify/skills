"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = default_1;
const path_1 = require("path");
const fs_1 = require("fs");
const SETTINGS_KEY = "pi-skills-installer.installedSkills";
const DEFAULT_SKILLS_DIR = (0, path_1.join)(process.env.HOME || "", ".pi", "agent", "skills");
function getInstalledSkills(pi) {
    const stored = pi.getSetting(SETTINGS_KEY);
    return stored ? JSON.parse(stored) : [];
}
function saveInstalledSkills(pi, skills) {
    pi.setSetting(SETTINGS_KEY, JSON.stringify(skills, null, 2));
}
function readSkillManifest(skillPath) {
    const manifestPath = (0, path_1.join)(skillPath, "SKILL.md");
    if (!(0, fs_1.existsSync)(manifestPath))
        return null;
    const content = (0, fs_1.readFileSync)(manifestPath, "utf-8");
    const frontmatterMatch = content.match(/^---([\s\S]*?)---/);
    if (!frontmatterMatch)
        return null;
    try {
        const yaml = frontmatterMatch[1].trim();
        const manifest = {};
        for (const line of yaml.split("\n")) {
            const [key, ...rest] = line.split(":");
            if (key && rest.length) {
                const value = rest.join(":").trim().replace(/^["']|["']$/g, "");
                manifest[key.trim()] = value;
            }
        }
        return manifest;
    }
    catch {
        return null;
    }
}
function discoverSkillsInDir(dir) {
    const skills = new Map();
    if (!(0, fs_1.existsSync)(dir))
        return skills;
    for (const category of (0, fs_1.readdirSync)(dir)) {
        const catPath = (0, path_1.join)(dir, category);
        if (!(0, fs_1.statSync)(catPath).isDirectory())
            continue;
        for (const skillName of (0, fs_1.readdirSync)(catPath)) {
            const skillPath = (0, path_1.join)(catPath, skillName);
            if (!(0, fs_1.statSync)(skillPath).isDirectory())
                continue;
            const manifest = readSkillManifest(skillPath);
            if (manifest?.name) {
                skills.set(manifest.name, skillPath);
            }
        }
    }
    return skills;
}
function ensureDir(dir) {
    if (!(0, fs_1.existsSync)(dir))
        (0, fs_1.mkdirSync)(dir, { recursive: true });
}
function parseArgs(args) {
    const parts = args.trim().split(/\s+/);
    const opts = { _: [] };
    for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        if (part.startsWith("--")) {
            const key = part.slice(2);
            const next = parts[i + 1];
            if (next && !next.startsWith("-")) {
                opts[key] = next;
                i++;
            }
            else {
                opts[key] = true;
            }
        }
        else if (part.startsWith("-") && part.length > 1) {
            for (const ch of part.slice(1)) {
                opts[ch] = true;
            }
        }
        else {
            opts._.push(part);
        }
    }
    return opts;
}
function default_1(pi) {
    pi.registerCommand("skill", {
        description: "Manage pi skills: add, list, remove, sync",
        getArgumentCompletions: (prefix) => {
            const subcommands = ["add", "list", "remove", "rm", "sync", "help"];
            return subcommands.filter(s => s.startsWith(prefix));
        },
        handler: async (args, ctx) => {
            const parsed = parseArgs(args);
            const subcommand = parsed._[0] || "help";
            try {
                let result;
                switch (subcommand) {
                    case "add":
                        result = await handleAdd(pi, ctx, parsed);
                        break;
                    case "list":
                        result = await handleList(pi, ctx);
                        break;
                    case "remove":
                    case "rm":
                        result = await handleRemove(pi, ctx, parsed);
                        break;
                    case "sync":
                        result = await handleSync(pi, ctx, parsed);
                        break;
                    case "help":
                    default:
                        result = showHelp();
                        break;
                }
                ctx.ui.notify(result, "info");
                return result;
            }
            catch (error) {
                const msg = `Error: ${error instanceof Error ? error.message : "Unknown error"}`;
                ctx.ui.notify(msg, "error");
                return msg;
            }
        },
    });
    // ============================================
    // SUB COMMANDS
    // ============================================
    async function handleAdd(pi, ctx, parsed) {
        const source = parsed._[1];
        if (!source) {
            return "Usage: pi skill add <source> [options]\n" +
                "  Sources:\n" +
                "    git:github.com/user/repo[@ref]     - Git repository\n" +
                "    npm:@scope/pkg[@version]           - NPM package\n" +
                "    ./local/path                       - Local directory\n" +
                "    github:user/repo[@ref]             - GitHub shorthand\n" +
                "  Options:\n" +
                "    --skill <name>                     - Specific skill(s) to install (comma-separated)\n" +
                "    --global, -g                       - Install globally (default)\n" +
                "    --local, -l                        - Install to project (.pi/skills/)";
        }
        const skillNames = parsed.skill ? parsed.skill.split(",").map((s) => s.trim()) : null;
        const isGlobal = !parsed.local && !parsed.l;
        if (source.startsWith("git:") || source.startsWith("github:")) {
            return await installFromGit(pi, source, skillNames, isGlobal);
        }
        else if (source.startsWith("npm:")) {
            return await installFromNpm(pi, source, skillNames, isGlobal);
        }
        else {
            return await installFromLocal(pi, source, skillNames, isGlobal);
        }
    }
    async function handleList(pi, ctx) {
        const skills = getInstalledSkills(pi);
        if (skills.length === 0)
            return "No skills installed.";
        let out = "Installed skills:\n\n";
        for (const s of skills) {
            out += `  ${s.name} (${s.sourceType}: ${s.source})\n`;
            out += `    Path: ${s.path}\n`;
            out += `    Description: ${s.manifest.description || "—"}\n`;
            out += `    Installed: ${s.installedAt}\n\n`;
        }
        return out.trim();
    }
    async function handleRemove(pi, ctx, parsed) {
        const name = parsed._[1];
        if (!name)
            return "Usage: pi skill remove <skill-name>";
        const skills = getInstalledSkills(pi);
        const idx = skills.findIndex(s => s.name === name);
        if (idx === -1)
            return `Skill '${name}' not found.`;
        const skill = skills[idx];
        try {
            (0, fs_1.rmSync)(skill.path, { recursive: true, force: true });
        }
        catch { /* ignore */ }
        skills.splice(idx, 1);
        saveInstalledSkills(pi, skills);
        return `Removed skill: ${name}`;
    }
    async function handleSync(pi, ctx, parsed) {
        const repoPath = parsed._[1] || "~/Documents/Projects/skills/skills";
        const resolved = (0, path_1.resolve)(repoPath.replace(/^~/, process.env.HOME || ""));
        if (!(0, fs_1.existsSync)(resolved))
            return `Repository not found: ${resolved}`;
        const skillNames = parsed.skill ? parsed.skill.split(",").map((s) => s.trim()) : null;
        const isGlobal = !parsed.local && !parsed.l;
        const discovered = discoverSkillsInDir(resolved);
        let installed = 0;
        let skipped = 0;
        for (const [name, path] of discovered) {
            if (skillNames && !skillNames.includes(name)) {
                skipped++;
                continue;
            }
            const targetDir = (0, path_1.join)(isGlobal ? DEFAULT_SKILLS_DIR : (0, path_1.join)(process.cwd(), ".pi", "skills"), name);
            ensureDir(dirname(targetDir));
            (0, fs_1.cpSync)(path, targetDir, { recursive: true });
            const manifest = readSkillManifest(targetDir);
            const skills = getInstalledSkills(pi);
            skills.push({
                name,
                source: resolved,
                sourceType: "local",
                path: targetDir,
                manifest,
                installedAt: new Date().toISOString()
            });
            saveInstalledSkills(pi, skills);
            installed++;
        }
        return `Synced from ${resolved}: ${installed} installed, ${skipped} skipped`;
    }
    // ============================================
    // INSTALLERS
    // ============================================
    async function installFromGit(pi, source, skillNames, isGlobal) {
        const url = source.replace(/^(git:|github:)/, "");
        const [repo, ref] = url.split("@");
        const repoName = repo.replace(/^github\.com\//, "").replace(/\//g, "-");
        const tempDir = (0, path_1.join)(process.env.TMPDIR || "/tmp", `pi-skill-${repoName}-${Date.now()}`);
        const targetDir = (0, path_1.join)(isGlobal ? DEFAULT_SKILLS_DIR : (0, path_1.join)(process.cwd(), ".pi", "skills"), repoName);
        // Clone
        const cloneCmd = `git clone --depth 1 ${ref ? `-b ${ref}` : ""} https://github.com/${repo}.git "${tempDir}"`;
        const result = await pi.bash(cloneCmd);
        if (result.exitCode !== 0) {
            throw new Error(`Git clone failed: ${result.stderr}`);
        }
        // Discover and copy skills
        const discovered = discoverSkillsInDir(tempDir);
        let count = 0;
        for (const [name, path] of discovered) {
            if (skillNames && !skillNames.includes(name))
                continue;
            const skillTarget = (0, path_1.join)(targetDir, name);
            ensureDir(dirname(skillTarget));
            (0, fs_1.cpSync)(path, skillTarget, { recursive: true });
            const manifest = readSkillManifest(skillTarget);
            const skills = getInstalledSkills(pi);
            skills.push({
                name,
                source: `git:${repo}${ref ? "@" + ref : ""}`,
                sourceType: "git",
                path: skillTarget,
                manifest,
                installedAt: new Date().toISOString()
            });
            saveInstalledSkills(pi, skills);
            count++;
        }
        // Cleanup
        (0, fs_1.rmSync)(tempDir, { recursive: true, force: true });
        return `Installed ${count} skill(s) from ${source}`;
    }
    async function installFromNpm(pi, source, skillNames, isGlobal) {
        const pkg = source.replace(/^npm:/, "");
        const [name, version] = pkg.split("@");
        const tempDir = (0, path_1.join)(process.env.TMPDIR || "/tmp", `pi-skill-${name.replace("/", "-")}-${Date.now()}`);
        const targetDir = (0, path_1.join)(isGlobal ? DEFAULT_SKILLS_DIR : (0, path_1.join)(process.cwd(), ".pi", "skills"), name.replace("/", "-"));
        // Pack and extract
        await pi.bash(`cd "${tempDir}" && npm pack ${pkg} 2>/dev/null || npm pack ${name}${version ? "@" + version : ""}`);
        await pi.bash(`cd "${tempDir}" && tar -xzf *.tgz`);
        const packageDir = (0, path_1.join)(tempDir, "package");
        const discovered = discoverSkillsInDir((0, path_1.join)(packageDir, "skills")) || discoverSkillsInDir(packageDir);
        let count = 0;
        for (const [skillName, path] of discovered) {
            if (skillNames && !skillNames.includes(skillName))
                continue;
            const skillTarget = (0, path_1.join)(targetDir, skillName);
            ensureDir(dirname(skillTarget));
            (0, fs_1.cpSync)(path, skillTarget, { recursive: true });
            const manifest = readSkillManifest(skillTarget);
            const skills = getInstalledSkills(pi);
            skills.push({
                name: skillName,
                source: `npm:${pkg}`,
                sourceType: "npm",
                path: skillTarget,
                manifest,
                installedAt: new Date().toISOString()
            });
            saveInstalledSkills(pi, skills);
            count++;
        }
        (0, fs_1.rmSync)(tempDir, { recursive: true, force: true });
        return `Installed ${count} skill(s) from ${source}`;
    }
    async function installFromLocal(pi, source, skillNames, isGlobal) {
        const resolved = (0, path_1.resolve)(source.replace(/^~/, process.env.HOME || ""));
        const discovered = discoverSkillsInDir(resolved);
        let count = 0;
        for (const [name, path] of discovered) {
            if (skillNames && !skillNames.includes(name))
                continue;
            const targetDir = (0, path_1.join)(isGlobal ? DEFAULT_SKILLS_DIR : (0, path_1.join)(process.cwd(), ".pi", "skills"), name);
            ensureDir(dirname(targetDir));
            (0, fs_1.cpSync)(path, targetDir, { recursive: true });
            const manifest = readSkillManifest(targetDir);
            const skills = getInstalledSkills(pi);
            skills.push({
                name,
                source: resolved,
                sourceType: "local",
                path: targetDir,
                manifest,
                installedAt: new Date().toISOString()
            });
            saveInstalledSkills(pi, skills);
            count++;
        }
        return `Installed ${count} skill(s) from ${resolved}`;
    }
    function showHelp() {
        return `pi skill - Manage skills for pi coding agent

Usage:
  pi skill add <source> [options]     Install skills
  pi skill list                       List installed skills
  pi skill remove <name>              Remove a skill
  pi skill sync [path] [options]      Sync from skills repository
  pi skill help                       Show this help

Sources for 'add':
  git:github.com/user/repo[@ref]     Git repository (branch/tag/commit)
  github:user/repo[@ref]             GitHub shorthand
  npm:@scope/pkg[@version]           NPM package with pi-package keyword
  ./local/path                       Local directory with skills/

Options:
  --skill <name>                     Specific skill(s) to install (comma-separated)
  --global, -g                       Install globally to ~/.pi/agent/skills/ (default)
  --local, -l                        Install to project .pi/skills/

Examples:
  pi skill add git:github.com/quokkify/skills --skill '*'
  pi skill add npm:@quokkify/pi-skills --skill orchestrator-workflow
  pi skill add ~/my-skills --skill code-review
  pi skill sync ~/Documents/Projects/skills/skills --skill '*' -g
  pi skill list
  pi skill remove orchestrator-workflow`;
    }
}
// Helper for dirname since we removed the import
function dirname(path) {
    return path.split("/").slice(0, -1).join("/") || "/";
}
//# sourceMappingURL=index.js.map