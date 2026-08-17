import { join, resolve } from "path";
import { existsSync, mkdirSync, readdirSync, statSync, cpSync, rmSync, readFileSync } from "fs";

// Type declarations matching pi's ExtensionAPI
interface ExtensionAPI {
  registerCommand(name: string, command: CommandDefinition): void;
  getSetting(key: string): any;
  setSetting(key: string, value: any): void;
  notify(message: string, level?: "info" | "warning" | "error"): void;
  bash(command: string, options?: BashOptions): Promise<BashResult>;
  log(level: "debug" | "info" | "warn" | "error", message: string): void;
}

interface CommandDefinition {
  description: string;
  handler: (args: string, ctx: CommandContext) => Promise<string | void>;
  getArgumentCompletions?: (prefix: string) => string[] | null;
}

interface CommandContext {
  ui: {
    notify(message: string, level: "info" | "warning" | "error"): void;
    select(title: string, items: string[]): Promise<string | null>;
    confirm(title: string, message: string): Promise<boolean>;
  };
  session: any;
}

interface BashOptions {
  cwd?: string;
  env?: Record<string, string>;
  timeout?: number;
  signal?: AbortSignal;
}

interface BashResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  signal?: string;
}

interface SkillManifest {
  name: string;
  description: string;
  license?: string;
  compatibility?: string;
  metadata?: Record<string, any>;
  "allowed-tools"?: string;
  "disable-model-invocation"?: boolean;
}

interface InstalledSkill {
  name: string;
  source: string;
  sourceType: "git" | "npm" | "local" | "github";
  path: string;
  manifest: SkillManifest;
  installedAt: string;
}

const SETTINGS_KEY = "pi-skills-installer.installedSkills";
const DEFAULT_SKILLS_DIR = join(process.env.HOME || "", ".pi", "agent", "skills");

function getInstalledSkills(pi: ExtensionAPI): InstalledSkill[] {
  const stored = pi.getSetting(SETTINGS_KEY);
  return stored ? JSON.parse(stored) : [];
}

function saveInstalledSkills(pi: ExtensionAPI, skills: InstalledSkill[]): void {
  pi.setSetting(SETTINGS_KEY, JSON.stringify(skills, null, 2));
}

function readSkillManifest(skillPath: string): SkillManifest | null {
  const manifestPath = join(skillPath, "SKILL.md");
  if (!existsSync(manifestPath)) return null;

  const content = readFileSync(manifestPath, "utf-8");
  const frontmatterMatch = content.match(/^---([\s\S]*?)---/);
  if (!frontmatterMatch) return null;

  try {
    const yaml = frontmatterMatch[1].trim();
    const manifest: Partial<SkillManifest> = {};
    for (const line of yaml.split("\n")) {
      const [key, ...rest] = line.split(":");
      if (key && rest.length) {
        const value = rest.join(":").trim().replace(/^["']|["']$/g, "");
        (manifest as any)[key.trim()] = value;
      }
    }
    return manifest as SkillManifest;
  } catch {
    return null;
  }
}

function discoverSkillsInDir(dir: string): Map<string, string> {
  const skills = new Map<string, string>();
  if (!existsSync(dir)) return skills;

  for (const category of readdirSync(dir)) {
    const catPath = join(dir, category);
    if (!statSync(catPath).isDirectory()) continue;

    for (const skillName of readdirSync(catPath)) {
      const skillPath = join(catPath, skillName);
      if (!statSync(skillPath).isDirectory()) continue;

      const manifest = readSkillManifest(skillPath);
      if (manifest?.name) {
        skills.set(manifest.name, skillPath);
      }
    }
  }
  return skills;
}

function ensureDir(dir: string): void {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function parseArgs(args: string): Record<string, any> {
  const parts = args.trim().split(/\s+/);
  const opts: Record<string, any> = { _: [] };
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (part.startsWith("--")) {
      const key = part.slice(2);
      const next = parts[i + 1];
      if (next && !next.startsWith("-")) {
        opts[key] = next;
        i++;
      } else {
        opts[key] = true;
      }
    } else if (part.startsWith("-") && part.length > 1) {
      for (const ch of part.slice(1)) {
        opts[ch] = true;
      }
    } else {
      opts._.push(part);
    }
  }
  return opts;
}

export default function (pi: ExtensionAPI) {
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
        let result: string;

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
      } catch (error) {
        const msg = `Error: ${error instanceof Error ? error.message : "Unknown error"}`;
        ctx.ui.notify(msg, "error");
        return msg;
      }
    },
  });

  // ============================================
  // SUB COMMANDS
  // ============================================

  async function handleAdd(pi: ExtensionAPI, ctx: CommandContext, parsed: Record<string, any>): Promise<string> {
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

    const skillNames = parsed.skill ? parsed.skill.split(",").map((s: string) => s.trim()) : null;
    const isGlobal = !parsed.local && !parsed.l;

    if (source.startsWith("git:") || source.startsWith("github:")) {
      return await installFromGit(pi, source, skillNames, isGlobal);
    } else if (source.startsWith("npm:")) {
      return await installFromNpm(pi, source, skillNames, isGlobal);
    } else {
      return await installFromLocal(pi, source, skillNames, isGlobal);
    }
  }

  async function handleList(pi: ExtensionAPI, ctx: CommandContext): Promise<string> {
    const skills = getInstalledSkills(pi);
    if (skills.length === 0) return "No skills installed.";

    let out = "Installed skills:\n\n";
    for (const s of skills) {
      out += `  ${s.name} (${s.sourceType}: ${s.source})\n`;
      out += `    Path: ${s.path}\n`;
      out += `    Description: ${s.manifest.description || "—"}\n`;
      out += `    Installed: ${s.installedAt}\n\n`;
    }
    return out.trim();
  }

  async function handleRemove(pi: ExtensionAPI, ctx: CommandContext, parsed: Record<string, any>): Promise<string> {
    const name = parsed._[1];
    if (!name) return "Usage: pi skill remove <skill-name>";

    const skills = getInstalledSkills(pi);
    const idx = skills.findIndex(s => s.name === name);

    if (idx === -1) return `Skill '${name}' not found.`;

    const skill = skills[idx];
    try {
      rmSync(skill.path, { recursive: true, force: true });
    } catch { /* ignore */ }

    skills.splice(idx, 1);
    saveInstalledSkills(pi, skills);

    return `Removed skill: ${name}`;
  }

  async function handleSync(pi: ExtensionAPI, ctx: CommandContext, parsed: Record<string, any>): Promise<string> {
    const repoPath = parsed._[1] || "~/Documents/Projects/skills/skills";
    const resolved = resolve(repoPath.replace(/^~/, process.env.HOME || ""));

    if (!existsSync(resolved)) return `Repository not found: ${resolved}`;

    const skillNames = parsed.skill ? parsed.skill.split(",").map((s: string) => s.trim()) : null;
    const isGlobal = !parsed.local && !parsed.l;

    const discovered = discoverSkillsInDir(resolved);
    let installed = 0;
    let skipped = 0;

    for (const [name, path] of discovered) {
      if (skillNames && !skillNames.includes(name)) {
        skipped++;
        continue;
      }

      const targetDir = join(isGlobal ? DEFAULT_SKILLS_DIR : join(process.cwd(), ".pi", "skills"), name);
      ensureDir(dirname(targetDir));
      cpSync(path, targetDir, { recursive: true });

      const manifest = readSkillManifest(targetDir)!;
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

  async function installFromGit(pi: ExtensionAPI, source: string, skillNames: string[] | null, isGlobal: boolean): Promise<string> {
    const url = source.replace(/^(git:|github:)/, "");
    const [repo, ref] = url.split("@");
    const repoName = repo.replace(/^github\.com\//, "").replace(/\//g, "-");

    const tempDir = join(process.env.TMPDIR || "/tmp", `pi-skill-${repoName}-${Date.now()}`);
    const targetDir = join(isGlobal ? DEFAULT_SKILLS_DIR : join(process.cwd(), ".pi", "skills"), repoName);

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
      if (skillNames && !skillNames.includes(name)) continue;

      const skillTarget = join(targetDir, name);
      ensureDir(dirname(skillTarget));
      cpSync(path, skillTarget, { recursive: true });

      const manifest = readSkillManifest(skillTarget)!;
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
    rmSync(tempDir, { recursive: true, force: true });

    return `Installed ${count} skill(s) from ${source}`;
  }

  async function installFromNpm(pi: ExtensionAPI, source: string, skillNames: string[] | null, isGlobal: boolean): Promise<string> {
    const pkg = source.replace(/^npm:/, "");
    const [name, version] = pkg.split("@");

    const tempDir = join(process.env.TMPDIR || "/tmp", `pi-skill-${name.replace("/", "-")}-${Date.now()}`);
    const targetDir = join(isGlobal ? DEFAULT_SKILLS_DIR : join(process.cwd(), ".pi", "skills"), name.replace("/", "-"));

    // Pack and extract
    await pi.bash(`cd "${tempDir}" && npm pack ${pkg} 2>/dev/null || npm pack ${name}${version ? "@" + version : ""}`);
    await pi.bash(`cd "${tempDir}" && tar -xzf *.tgz`);

    const packageDir = join(tempDir, "package");
    const discovered = discoverSkillsInDir(join(packageDir, "skills")) || discoverSkillsInDir(packageDir);
    let count = 0;

    for (const [skillName, path] of discovered) {
      if (skillNames && !skillNames.includes(skillName)) continue;

      const skillTarget = join(targetDir, skillName);
      ensureDir(dirname(skillTarget));
      cpSync(path, skillTarget, { recursive: true });

      const manifest = readSkillManifest(skillTarget)!;
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

    rmSync(tempDir, { recursive: true, force: true });

    return `Installed ${count} skill(s) from ${source}`;
  }

  async function installFromLocal(pi: ExtensionAPI, source: string, skillNames: string[] | null, isGlobal: boolean): Promise<string> {
    const resolved = resolve(source.replace(/^~/, process.env.HOME || ""));
    const discovered = discoverSkillsInDir(resolved);
    let count = 0;

    for (const [name, path] of discovered) {
      if (skillNames && !skillNames.includes(name)) continue;

      const targetDir = join(isGlobal ? DEFAULT_SKILLS_DIR : join(process.cwd(), ".pi", "skills"), name);
      ensureDir(dirname(targetDir));
      cpSync(path, targetDir, { recursive: true });

      const manifest = readSkillManifest(targetDir)!;
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

  function showHelp(): string {
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
function dirname(path: string): string {
  return path.split("/").slice(0, -1).join("/") || "/";
}