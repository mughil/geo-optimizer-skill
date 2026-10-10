#!/usr/bin/env node
// Publish only the content this fork can actually serve; the upstream commercial
// frontend depends on GeoReady accounts, APIs, analytics, and legal policies.
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createClient } from '@sanity/client';
import { createImageUrlBuilder } from '@sanity/image-url';
import { toHTML } from '@portabletext/to-html';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const output = join(root, 'dist');
const site = 'https://geooptimizer.netlify.app';
const projectId = 'ov1pl2ik';
const client = createClient({ projectId, dataset: 'production', apiVersion: '2024-01-01', useCdn: false });
const image = createImageUrlBuilder(client);
const escape = (value = '') => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const slugPath = (article) => article.category === 'resources' ? 'resources' : 'guides';
const url = (article) => `${site}/${slugPath(article)}/${encodeURIComponent(article.slug.current)}/`;
const css = `:root{font-family:system-ui,sans-serif;color:#17221b;background:#fafbf8}body{margin:0}header,main,footer{max-width:780px;margin:auto;padding:1.5rem}header{display:flex;gap:1.5rem;align-items:center;border-bottom:1px solid #cbd5cc}a{color:#176743}header a:first-child{font-weight:700;font-size:1.2rem}h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.1}h2{margin-top:2.5rem}p,li{line-height:1.7}article img{max-width:100%;height:auto}nav a{display:inline-block;margin-right:1rem}small,.muted{color:#53645b}footer{border-top:1px solid #cbd5cc}.card{border-bottom:1px solid #dce4dc;padding:1rem 0}.card h2{margin:.2rem 0;font-size:1.25rem}blockquote{border-left:3px solid #176743;padding-left:1rem}pre{overflow-x:auto;padding:1rem;background:#eaf0eb}`;
function page(title, description, canonical, body) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)} — GEO Optimizer</title><meta name="description" content="${escape(description)}"><link rel="canonical" href="${canonical}"><style>${css}</style></head><body><header><a href="/">GEO Optimizer</a><nav><a href="/guides/">Guides</a><a href="/resources/">Resources</a><a href="https://github.com/mughil/geo-optimizer-skill">Source code</a></nav></header><main>${body}</main><footer><small>Independent repository edition. Article authors are credited on each page. No signup, tracking, or paid service is offered here.</small></footer></body></html>`;
}
function save(path, content) {
  const directory = join(output, path);
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, 'index.html'), content);
}
const articles = await client.fetch(`*[_type == "article" && defined(slug.current) && (!defined(status) || status == "published") && category in ["guides", "resources"]] | order(datePublished desc){title, description, slug, category, datePublished, author, body, ogImage}`);
if (articles.length < 60) throw new Error(`Expected the migrated public collection; found only ${articles.length} articles.`);
const paths = new Set();
for (const article of articles) {
  const path = `${slugPath(article)}/${article.slug.current}`;
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(article.slug.current) || paths.has(path)) throw new Error(`Invalid or duplicate article path: ${path}`);
  paths.add(path);
}
const available = new Set(['/', '/guides/', '/resources/', ...[...paths].map((path) => `/${path}/`)]);
function removeUnavailableLinks(html) {
  return html.replace(/<a\b([^>]*?)href="(\/[^"#?]*\/?)"([^>]*)>(.*?)<\/a>/gs, (match, before, href, after, label) => available.has(href) ? match : label);
}
rmSync(output, { recursive: true, force: true });
for (const article of articles) {
  const canonical = url(article);
  const body = toHTML(article.body ?? [], { components: { types: {
    image: ({ value }) => value?.asset?._ref ? `<figure><img loading="lazy" src="${escape(image.image(value).width(1200).auto('format').url())}" alt="${escape(value.alt)}"></figure>` : '',
    callout: ({ value }) => `<blockquote><strong>${escape(value.variant ?? 'Info')}</strong><p>${escape(value.body)}</p></blockquote>`,
    codeBlock: ({ value }) => `<pre><code>${escape(value.code)}</code></pre>`,
  } } });
  const byline = article.author ? `<p class="muted">By ${escape(article.author)}</p>` : '';
  save(`${slugPath(article)}/${article.slug.current}`, page(article.title, article.description, canonical, `<article><p><a href="/${slugPath(article)}/">← All ${slugPath(article)}</a></p><h1>${escape(article.title)}</h1>${byline}<p class="muted">${escape(article.datePublished?.slice(0, 10))}</p><p>${escape(article.description)}</p>${removeUnavailableLinks(body)}</article>`));
}
for (const section of ['guides', 'resources']) {
  const cards = articles.filter((article) => slugPath(article) === section).map((article) => `<div class="card"><h2><a href="/${section}/${encodeURIComponent(article.slug.current)}/">${escape(article.title)}</a></h2><p>${escape(article.description)}</p><small>${escape(article.datePublished?.slice(0, 10))}</small></div>`).join('');
  save(section, page(`${section[0].toUpperCase()}${section.slice(1)}`, `Public ${section} from the GEO Optimizer repository`, `${site}/${section}/`, `<h1>${section[0].toUpperCase()}${section.slice(1)}</h1><p>Public articles, with their original authors credited.</p>${cards}`));
}
save('', page('Home', 'GEO Optimizer articles and open-source code', `${site}/`, '<h1>GEO Optimizer</h1><p>Explore the public guides and resources from this repository. This independent edition does not operate the original GeoReady audit, accounts, newsletter, or paid plans.</p><p><a href="/guides/">Read guides</a> · <a href="/resources/">Read resources</a> · <a href="https://github.com/mughil/geo-optimizer-skill">View source code</a></p>'));
const locations = ['/', '/guides/', '/resources/', ...articles.map((article) => new URL(url(article)).pathname)];
writeFileSync(join(output, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${locations.map((location) => `<url><loc>${site}${location}</loc></url>`).join('')}</urlset>`);
writeFileSync(join(output, 'robots.txt'), `User-agent: *\nAllow: /\nSitemap: ${site}/sitemap.xml\n`);
console.log(`Built ${articles.length} articles for ${site}`);
