import net from 'node:net';

const SHIFT_STEP = 10;

function isFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.listen(port, '127.0.0.1', () => server.close(() => resolve(true)));
  });
}

export async function findFreePorts(base, { maxShift = 20 } = {}) {
  for (let shift = 0; shift <= maxShift; shift += SHIFT_STEP) {
    const ports = Object.fromEntries(Object.entries(base).map(([name, port]) => [name, port + shift]));
    const free = await Promise.all(Object.values(ports).map(isFree));
    if (free.every(Boolean)) return ports;
  }
  throw new Error(`no free port set found for ${JSON.stringify(base)} (maxShift ${maxShift})`);
}
