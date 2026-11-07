#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { spawnSync } from 'node:child_process';
import { openSync, closeSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { findFreePorts } from './lib/ports.mjs';

const EXIT_USAGE = 64;
const EXIT_COMPOSE = 2;
const LOG_TAIL_LINES = 50;
const COMMANDS = ['up', 'seed', 'reset', 'down'];

function usage(message) {
  console.error(`${message}\nusage: stand.mjs <${COMMANDS.join('|')}> --config <abs path> --worktree <dir> --project <name> [--dry-run]`);
  process.exit(EXIT_USAGE);
}

let parsed;
try {
  parsed = parseArgs({
    allowPositionals: true,
    options: {
      config: { type: 'string' },
      worktree: { type: 'string' },
      project: { type: 'string' },
      'dry-run': { type: 'boolean', default: false },
    },
  });
} catch (err) {
  usage(err.message);
}
const { values, positionals } = parsed;
const [command] = positionals;
if (!COMMANDS.includes(command)) usage(`unknown or missing command: ${command ?? '(none)'}`);
for (const flag of ['config', 'worktree', 'project']) {
  if (!values[flag]) usage(`missing --${flag}`);
}

const worktree = path.resolve(values.worktree);
const project = values.project;
const dryRun = values['dry-run'];
const configPath = path.resolve(values.config);
const config = (await import(pathToFileURL(configPath).href)).default;
const composeFiles = config.compose.files.flatMap((f) => ['-f', path.resolve(worktree, f)]);
const composeBase = ['compose', ...composeFiles, '--project-directory', worktree, '-p', project];

function compose(args, { stdin = 'inherit' } = {}) {
  const result = spawnSync('docker', [...composeBase, ...args], { cwd: worktree, stdio: [stdin, 'inherit', 'inherit'] });
  if (result.status !== 0) {
    const logs = spawnSync('docker', [...composeBase, 'logs', '--tail', String(LOG_TAIL_LINES)], { cwd: worktree, encoding: 'utf8' });
    process.stderr.write(`${logs.stdout ?? ''}${logs.stderr ?? ''}`.split('\n').slice(-LOG_TAIL_LINES).join('\n'));
    console.error(`docker compose ${args[0]} failed (status ${result.status})`);
    process.exit(EXIT_COMPOSE);
  }
}

function runStep(step, name) {
  if (!step) {
    console.error(`config has no "${name}" step`);
    process.exit(EXIT_USAGE);
  }
  if (step.command) {
    const [cmd, ...args] = step.command;
    if (dryRun) return console.log(JSON.stringify({ project, run: step.command, cwd: worktree }));
    const result = spawnSync(cmd, args, { cwd: worktree, stdio: 'inherit' });
    if (result.status !== 0) process.exit(result.status ?? 1);
    return;
  }
  const args = ['exec', '-T', step.service, 'sh', '-c', step.run];
  // The script belongs to the adapter, which the MR head may not contain.
  const script = path.resolve(path.dirname(configPath), step.script);
  if (dryRun) return console.log(JSON.stringify({ project, compose: args, stdin: script }));
  const fd = openSync(script, 'r');
  try {
    compose(args, { stdin: fd });
  } finally {
    closeSync(fd);
  }
}

if (command === 'up') {
  const ports = await findFreePorts(config.compose.ports);
  const baseUrl = config.baseUrl({ ports });
  const plan = { project, ports, baseUrl };
  if (!dryRun) {
    const env = { ...config.compose.env, ...ports, COMPOSE_PROJECT_NAME: project };
    writeFileSync(path.join(worktree, '.env'), Object.entries(env).map(([k, v]) => `${k}=${v}`).join('\n') + '\n');
    compose(['up', '-d', '--build', '--wait']);
  }
  console.log(JSON.stringify(plan));
} else if (command === 'seed' || command === 'reset') {
  runStep(config[command], command);
} else if (dryRun) {
  console.log(JSON.stringify({ project, compose: ['down', '-v'] }));
} else {
  compose(['down', '-v']);
}
