// Uso: node render.mjs --spec spec.json --out salida.mp4
// spec.json: {"composition": "counter|compare|steps", "props": {...}}
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const arg = (name) => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : undefined;
};

const specPath = arg('spec');
const out = arg('out');
if (!specPath || !out) {
  console.error('Faltan --spec y --out');
  process.exit(2);
}
const spec = JSON.parse(fs.readFileSync(specPath, 'utf-8'));
const browserExecutable = process.env.REMOTION_BROWSER || null;

const bundled = await bundle({entryPoint: path.join(here, 'src', 'index.ts')});
const composition = await selectComposition({
  serveUrl: bundled,
  id: spec.composition,
  inputProps: spec.props,
  browserExecutable,
});
await renderMedia({
  composition,
  serveUrl: bundled,
  codec: 'h264',
  outputLocation: out,
  inputProps: spec.props,
  browserExecutable,
  logLevel: 'error',
});
console.log(out);
