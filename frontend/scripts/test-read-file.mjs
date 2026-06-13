/**
 * Integration smoke test: POST /read-file with local .sav
 * Run: node scripts/test-read-file.mjs
 * Requires backend at VITE_API_URL (default http://localhost:8765)
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const API = process.env.VITE_API_URL || 'http://localhost:8765';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const savPath = path.resolve(__dirname, '../../testdata/kemal.büsra.sav');

async function main() {
  if (!fs.existsSync(savPath)) {
    console.log('SKIP: test SAV not found at', savPath);
    process.exit(0);
  }

  const blob = new Blob([fs.readFileSync(savPath)]);
  const form = new FormData();
  form.append('file', blob, 'kemal.büsra.sav');

  const res = await fetch(`${API}/read-file`, { method: 'POST', body: form });
  if (!res.ok) {
    const text = await res.text();
    console.error('FAIL: read-file', res.status, text);
    process.exit(1);
  }

  const json = await res.json();
  const rows = json.data?.length ?? 0;
  const cols = json.columns?.length ?? Object.keys(json.data?.[0] ?? {}).length;
  console.log(`OK: ${rows} rows, ${cols} columns, source=${json.source}, labels=${json.labels_found ?? 0}`);
  if (rows < 1 || cols < 1) {
    console.error('FAIL: empty parse result');
    process.exit(1);
  }
}

main().catch((e) => {
  if (e.cause?.code === 'ECONNREFUSED' || e.message?.includes('fetch failed')) {
    console.log('SKIP: backend not running at', API);
    process.exit(0);
  }
  console.error('FAIL:', e.message);
  process.exit(1);
});
