#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const START = '<!-- demo:start -->';
const END = '<!-- demo:end -->';
const BLOCK_RE = /<!-- demo:start -->[\s\S]*?<!-- demo:end -->/;

function formatDuration(sec) {
  const total = Math.floor(sec);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function section(heading, lines) {
  return lines.length ? [`### ${heading}`, ...lines, ''] : [];
}

function buildContent({ covers = {}, notShown = [], questions = [], sha, durationSec, videoUrl }) {
  return [
    `Видео: ${videoUrl}`,
    `Коммит: \`${sha}\``,
    `Длительность: ${formatDuration(durationSec)}`,
    '',
    ...section('Показано', Object.entries(covers).map(([id, text]) => `- ${id}: ${text}`)),
    ...section('Вопросы к клиентке', questions.map((q) => `- ${q}`)),
    ...section('Не показано', notShown.map((n) => `- ${n}`)),
  ].join('\n').trimEnd();
}

export function buildSummary(input) {
  return `# ${input.title}\n\n${buildContent(input)}\n`;
}

export function buildDemoBlock(input) {
  return `${START}\n## Demo\n\n${buildContent(input)}\n${END}`;
}

export function replaceDemoBlock(body, block) {
  const normalized = body.replace(/\r\n?/g, '\n');
  if (BLOCK_RE.test(normalized)) {
    return { body: normalized.replace(BLOCK_RE, () => block), replaced: true };
  }
  if (normalized.trim() === '') return { body: block, replaced: false };
  return { body: `${normalized.replace(/\n+$/, '')}\n\n${block}`, replaced: false };
}

function usage(message) {
  process.stderr.write(`${message}\nusage: summary.mjs md|block --scenario-json <f> --sha <sha> --duration <sec> --video-url <url>\n       summary.mjs replace --body-file <f> --block-file <f>\n`);
  process.exit(64);
}

function main(argv) {
  const [cmd, ...rest] = argv;
  let values;
  try {
    ({ values } = parseArgs({
      args: rest,
      options: {
        'scenario-json': { type: 'string' },
        sha: { type: 'string' },
        duration: { type: 'string' },
        'video-url': { type: 'string' },
        'body-file': { type: 'string' },
        'block-file': { type: 'string' },
      },
    }));
  } catch (e) {
    usage(e.message);
  }

  if (cmd === 'md' || cmd === 'block') {
    const duration = Number(values.duration);
    if (!values['scenario-json'] || !values.sha || !values['video-url'] || values.duration === undefined || !Number.isFinite(duration) || duration < 0) {
      usage('missing or invalid option');
    }
    const scenario = JSON.parse(readFileSync(values['scenario-json'], 'utf8'));
    const input = { ...scenario, sha: values.sha, durationSec: duration, videoUrl: values['video-url'] };
    process.stdout.write(cmd === 'md' ? buildSummary(input) : `${buildDemoBlock(input)}\n`);
  } else if (cmd === 'replace') {
    if (!values['body-file'] || !values['block-file']) usage('missing option');
    const block = readFileSync(values['block-file'], 'utf8').replace(/\r\n?/g, '\n').trimEnd();
    const { body, replaced } = replaceDemoBlock(readFileSync(values['body-file'], 'utf8'), block);
    process.stdout.write(body);
    process.stderr.write(`replaced=${replaced}\n`);
  } else {
    usage(`unknown command: ${cmd ?? '(none)'}`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2));
}
