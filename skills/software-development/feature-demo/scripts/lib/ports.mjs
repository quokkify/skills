import net from 'node:net';

const SHIFT_STEP = 10;
// A port is free only if it binds on every interface: Docker publishes on 0.0.0.0, and on macOS
// a loopback-only probe succeeds even while another process holds the wildcard address.
const PROBE_HOSTS = ['0.0.0.0', '127.0.0.1', '::'];
const IPV6_UNAVAILABLE = new Set(['EADDRNOTAVAIL', 'EAFNOSUPPORT']);

function bindable(port, host) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', (err) => resolve(host === '::' && IPV6_UNAVAILABLE.has(err.code)));
    server.listen(port, host, () => server.close(() => resolve(true)));
  });
}

async function isFree(port) {
  for (const host of PROBE_HOSTS) {
    if (!(await bindable(port, host))) return false;
  }
  return true;
}

export async function findFreePorts(base, { maxShift = 20 } = {}) {
  for (let shift = 0; shift <= maxShift; shift += SHIFT_STEP) {
    const ports = Object.fromEntries(Object.entries(base).map(([name, port]) => [name, port + shift]));
    const free = await Promise.all(Object.values(ports).map(isFree));
    if (free.every(Boolean)) return ports;
  }
  throw new Error(`no free port set found for ${JSON.stringify(base)} (maxShift ${maxShift})`);
}
