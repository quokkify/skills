#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const START = '<!-- demo:start -->';
const END = '<!-- demo:end -->';
const BLOCK_RE = /<!-- demo:start -->[\s\S]*?<!-- demo:end -->/;
const DEFAULT_LANG = 'en';
const LABELS = {
  en: { video: 'Video', commit: 'Commit', duration: 'Duration', shown: 'Shown', questions: 'Open questions', notShown: 'Not shown' },
  ru: { video: 'Видео', commit: 'Коммит', duration: 'Длительность', shown: 'Показано', questions: 'Открытые вопросы', notShown: 'Не показано' },
};

function labelsFor(lang = DEFAULT_LANG) {
  if (!Object.hasOwn(LABELS, lang)) throw new Error(`unknown lang: ${lang} (expected ${Object.keys(LABELS).join('|')})`);
  return LABELS[lang];
}

function formatDuration(sec) {
  const total = Math.floor(sec);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function section(heading, lines) {
  return lines.length ? [`### ${heading}`, ...lines, ''] : [];
}

function buildContent({ covers = {}, notShown = [], questions = [], sha, durationSec, videoUrl, note, lang }) {
  const l = labelsFor(lang);
  return [
    `${l.video}: ${videoUrl}`,
    `${l.commit}: \`${sha}\``,
    `${l.duration}: ${formatDuration(durationSec)}`,
    ...(note ? [note] : []),
    '',
    ...section(l.shown, Object.entries(covers).map(([id, text]) => `- ${id}: ${text}`)),
    ...section(l.questions, questions.map((q) => `- ${q}`)),
    ...section(l.notShown, notShown.map((n) => `- ${n}`)),
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
  process.stderr.write(`${message}\nusage: summary.mjs md|block --scenario-json <f> --sha <sha> --duration <sec> --video-url <url> [--lang en|ru] [--note <text>]\n       summary.mjs replace --body-file <f> --block-file <f>\n`);
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
        lang: { type: 'string', default: DEFAULT_LANG },
        note: { type: 'string' },
      },
    }));
  } catch (e) {
    usage(e.message);
  }

  if (!Object.hasOwn(LABELS, values.lang)) usage(`unknown lang: ${values.lang}`);

  if (cmd === 'md' || cmd === 'block') {
    const duration = Number(values.duration);
    if (!values['scenario-json'] || !values.sha || !values['video-url'] || values.duration === undefined || !Number.isFinite(duration) || duration < 0) {
      usage('missing or invalid option');
    }
    const scenario = JSON.parse(readFileSync(values['scenario-json'], 'utf8'));
    const input = { ...scenario, sha: values.sha, durationSec: duration, videoUrl: values['video-url'], note: values.note, lang: values.lang };
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
