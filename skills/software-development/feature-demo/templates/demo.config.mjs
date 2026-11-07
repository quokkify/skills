// Project adapter for the feature-demo skill. Copy into the project (for example
// tools/demo/demo.config.mjs) and replace every value below; all of them are placeholders.
import { fileURLToPath } from 'node:url';

export default {
  compose: {
    // Relative to the worktree root.
    files: ['docker-compose.yml'],
    // Written to <worktree>/.env together with the chosen ports. Synthetic values only.
    env: { APP_ENV: 'demo', SEED_DEMO_DATA: 'true' },
    // Base ports; the whole set shifts by 10 (up to +20) until every port is free.
    ports: { FRONTEND_PORT: 4183, BACKEND_PORT: 4184, DB_PORT: 4185 },
  },
  baseUrl: ({ ports }) => `http://localhost:${ports.FRONTEND_PORT}`,
  // `script` is piped to `run` inside the compose `service`; it is relative to this file, not the worktree.
  seed: { service: 'backend', script: 'seed.py', run: 'python manage.py shell' },
  // Projects without such a shell run a host command in the worktree instead.
  reset: { command: ['npm', 'run', 'demo:reset'] },
  // Runs before the recording starts. Never type secrets inside a scenario.
  async login(page, { baseUrl }) {
    const password = process.env.DEMO_PASSWORD;
    if (!password) throw new Error('DEMO_PASSWORD is not set; export the demo account password before recording');
    await page.goto(`${baseUrl}/login`);
    await page.getByLabel('Email').fill('demo@example.com');
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByRole('navigation').waitFor();
  },
  // Caption language (en or ru); also passed to publish.sh as --lang for the MR block labels.
  captionsLang: 'en',
  viewport: { width: 1440, height: 900 },
  // Synthetic upload files used through kit.fixture(name).
  fixtures: fileURLToPath(new URL('./fixtures/', import.meta.url)),
};
