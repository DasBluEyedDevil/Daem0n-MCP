import * as esbuild from 'esbuild';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const isDev = process.argv.includes('--dev');

const result = await esbuild.build({
  entryPoints: [join(__dirname, 'd3-modules.js')],
  bundle: true,
  minify: !isDev,
  platform: 'browser',
  target: ['es2020'],
  format: 'iife',
  globalName: 'd3',  // Exposes as window.d3
  outfile: join(__dirname, '..', 'static', 'd3.bundle.js'),
  sourcemap: isDev ? 'inline' : false,
  treeShaking: true,
  metafile: true,
});

// Report bundle size
const outputSize = Object.values(result.metafile.outputs)[0].bytes;
console.log(`D3 bundle created: ${(outputSize / 1024).toFixed(1)} KB`);

if (isDev) {
  console.log('Development build with sourcemaps');
}
