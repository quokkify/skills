export default {
  compose: {
    files: ['docker-compose.yml'],
    env: { APP_MODE: 'demo' },
    ports: { FRONTEND_PORT: 4183, BACKEND_PORT: 4184, DB_PORT: 4185 },
  },
  baseUrl: ({ ports }) => `http://localhost:${ports.FRONTEND_PORT}`,
  seed: { service: 'backend', script: '.claude/demo/seed.py', run: 'python manage.py shell' },
  reset: { command: ['npm', 'run', 'reset'] },
};
