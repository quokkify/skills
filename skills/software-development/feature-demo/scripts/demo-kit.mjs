import path from 'node:path';
import { mkdirSync } from 'node:fs';

const DEFAULT_HOLD_MS = 3500;
const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function captionHtml(text) {
  const escaped = text.replace(/[&<>"']/g, (c) => ESCAPES[c]);
  return `<div data-demo-caption style="position:fixed;left:50%;bottom:32px;transform:translateX(-50%);max-width:80%;padding:12px 24px;border-radius:8px;background:rgba(0,0,0,.8);color:#fff;font:600 24px/1.3 sans-serif;text-align:center">${escaped}</div>`;
}

export function createKit(page, { shotsDir, fixturesDir, onShot } = {}) {
  let current;
  const hold = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function clearCaption() {
    if (!current) return;
    await current.dispose();
    current = undefined;
  }

  return {
    hold,
    async caption(text, holdMs = DEFAULT_HOLD_MS) {
      await clearCaption();
      if (text === '') return;
      current = await page.screencast.showOverlay(captionHtml(text));
      await hold(holdMs);
    },
    async chapter(title, description) {
      await page.screencast.showChapter(title, { description });
    },
    async shot(name) {
      mkdirSync(shotsDir, { recursive: true });
      const file = path.join(shotsDir, `${name}.png`);
      await page.screenshot({ path: file });
      await onShot?.(name);
      return file;
    },
    fixture: (name) => path.join(fixturesDir, name),
  };
}
