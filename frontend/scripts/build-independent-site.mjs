#!/usr/bin/env node
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const output = join(dirname(fileURLToPath(import.meta.url)), '..', 'dist');
const site = 'https://geooptimizer.netlify.app';
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,follow"><title>GEO Optimizer</title><meta name="description" content="GEO Optimizer open-source project repository"><link rel="canonical" href="${site}/"><style>:root{font-family:system-ui,sans-serif;color:#17221b;background:#fafbf8}body{margin:0}main,footer{max-width:720px;margin:auto;padding:2rem}h1{font-size:clamp(2rem,5vw,3.5rem)}p{line-height:1.7}a{color:#176743}footer{border-top:1px solid #cbd5cc;color:#53645b}</style></head><body><main><h1>GEO Optimizer</h1><p>This site accompanies the GEO Optimizer open-source repository. The imported articles and images are unavailable here while their publication rights are unconfirmed.</p><p><a href="https://github.com/mughil/geo-optimizer-skill">View the repository</a></p></main><footer><small>Original software copyright and MIT license are retained in the repository.</small></footer></body></html>`;

rmSync(output, { recursive: true, force: true });
mkdirSync(output, { recursive: true });
writeFileSync(join(output, 'index.html'), html);
writeFileSync(join(output, 'robots.txt'), 'User-agent: *\nDisallow: /\n');
console.log(`Built repository landing page for ${site}`);
