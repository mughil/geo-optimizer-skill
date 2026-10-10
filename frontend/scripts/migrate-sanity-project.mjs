#!/usr/bin/env node
// One-time, resumable migration of publicly readable articles and image assets.
// The target API token is supplied only through the GitHub Actions secret.

import { createClient } from '@sanity/client';
import { createHash } from 'node:crypto';

const sourceProjectId = process.env.SOURCE_SANITY_PROJECT_ID;
const targetProjectId = process.env.TARGET_SANITY_PROJECT_ID;
const dataset = process.env.SANITY_DATASET || 'production';
const mode = process.argv[2];

if (!sourceProjectId || !targetProjectId || sourceProjectId === targetProjectId) {
  throw new Error('Distinct SOURCE_SANITY_PROJECT_ID and TARGET_SANITY_PROJECT_ID are required.');
}
if (!['preflight', 'apply'].includes(mode)) {
  throw new Error('Choose preflight or apply.');
}
if (!process.env.SANITY_API_TOKEN) {
  throw new Error('SANITY_API_TOKEN is required for the target project.');
}

const source = createClient({ projectId: sourceProjectId, dataset, apiVersion: '2024-01-01', useCdn: false });
const target = createClient({ projectId: targetProjectId, dataset, apiVersion: '2024-01-01', useCdn: false, token: process.env.SANITY_API_TOKEN });
const query = '*[_type == "article" || _type == "sanity.imageAsset"]';
const sourceDocs = await source.fetch(query);
const articles = sourceDocs.filter((doc) => doc._type === 'article');
const assets = sourceDocs.filter((doc) => doc._type === 'sanity.imageAsset');
const sourceIds = new Set(sourceDocs.map((doc) => doc._id));

function collectReferences(value, result = new Set()) {
  if (!value || typeof value !== 'object') return result;
  if (typeof value._ref === 'string') result.add(value._ref);
  for (const child of Object.values(value)) collectReferences(child, result);
  return result;
}

const refs = new Set(articles.flatMap((article) => [...collectReferences(article)]));
const missingSourceRefs = [...refs].filter((id) => !sourceIds.has(id));
if (missingSourceRefs.length) throw new Error(`Source contains ${missingSourceRefs.length} unresolved references.`);
if (articles.length !== 84 || assets.length !== 84) {
  throw new Error(`Unexpected source inventory: ${articles.length} articles and ${assets.length} assets; review changes before migration.`);
}
if (assets.some((asset) => !asset.url || !asset.sha1hash)) {
  throw new Error('Every source asset must have a public URL and SHA-1 hash.');
}

const targetDocs = await target.fetch(query);
const targetArticleIds = new Set(targetDocs.filter((doc) => doc._type === 'article').map((doc) => doc._id));
const unexpectedTargetArticles = [...targetArticleIds].filter((id) => !sourceIds.has(id));
if (unexpectedTargetArticles.length) {
  throw new Error(`Target contains ${unexpectedTargetArticles.length} unrelated articles; migration will not overwrite them.`);
}
console.log(JSON.stringify({ mode, sourceArticles: articles.length, sourceAssets: assets.length, targetArticles: targetArticleIds.size, targetAssets: targetDocs.filter((doc) => doc._type === 'sanity.imageAsset').length, referencedAssets: refs.size }));
if (mode === 'preflight') process.exit(0);

const targetByHash = new Map(targetDocs.filter((doc) => doc._type === 'sanity.imageAsset').map((doc) => [doc.sha1hash, doc._id]));
const assetIdMap = new Map();
for (const [index, asset] of assets.entries()) {
  // The public CDN re-encodes JPEGs, so the source asset hash is not the hash
  // of publicly downloadable bytes. Request the highest available quality.
  const response = await fetch(`${asset.url}?q=100`);
  if (!response.ok) throw new Error(`Could not download source asset ${asset._id}: HTTP ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  const downloadHash = createHash('sha1').update(bytes).digest('hex');
  let targetId = targetByHash.get(downloadHash);
  if (!targetId) {
    const uploaded = await target.assets.upload('image', bytes, { filename: asset.originalFilename || `${asset.sha1hash}.${asset.extension}` });
    if (uploaded.sha1hash !== downloadHash) throw new Error(`Image hash changed during upload: ${asset._id}`);
    const sourceDimensions = asset.metadata?.dimensions;
    const targetDimensions = uploaded.metadata?.dimensions;
    if (sourceDimensions && targetDimensions && (sourceDimensions.width !== targetDimensions.width || sourceDimensions.height !== targetDimensions.height)) {
      throw new Error(`Image dimensions changed during upload: ${asset._id}`);
    }
    targetId = uploaded._id;
    targetByHash.set(downloadHash, targetId);
  }
  assetIdMap.set(asset._id, targetId);
  if ((index + 1) % 10 === 0 || index + 1 === assets.length) console.log(`Images verified: ${index + 1}/${assets.length}`);
}

function rewrite(value) {
  if (Array.isArray(value)) return value.map(rewrite);
  if (!value || typeof value !== 'object') return value;
  const output = {};
  for (const [key, child] of Object.entries(value)) {
    if (['_createdAt', '_updatedAt', '_rev', '_system'].includes(key)) continue;
    if (key === '_ref' && typeof child === 'string') {
      const mapped = assetIdMap.get(child);
      if (!mapped) throw new Error(`Unmapped article reference: ${child}`);
      output[key] = mapped;
    } else {
      output[key] = rewrite(child);
    }
  }
  return output;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
}

for (const [index, article] of articles.entries()) {
  await target.createIfNotExists(rewrite(article));
  if ((index + 1) % 10 === 0 || index + 1 === articles.length) console.log(`Articles verified: ${index + 1}/${articles.length}`);
}

const [importedArticles, importedAssets] = await Promise.all([
  target.fetch('*[_type == "article"]'),
  target.fetch('*[_type == "sanity.imageAsset"]{_id, sha1hash}'),
]);
const importedById = new Map(importedArticles.map((doc) => [doc._id, doc]));
const importedAssetIds = new Set(importedAssets.map((doc) => doc._id));
for (const article of articles) {
  const expected = rewrite(article);
  const actual = importedById.get(article._id);
  if (!actual) throw new Error(`Missing imported article: ${article._id}`);
  for (const [key, value] of Object.entries(expected)) {
    if (JSON.stringify(canonical(actual[key])) !== JSON.stringify(canonical(value))) throw new Error(`Imported field differs: ${article._id}.${key}`);
  }
  for (const ref of collectReferences(actual)) {
    if (!importedAssetIds.has(ref)) throw new Error(`Missing imported image reference: ${article._id} -> ${ref}`);
  }
}
if (importedArticles.length !== articles.length || importedAssets.length < assets.length) {
  throw new Error(`Target counts differ: ${importedArticles.length} articles, ${importedAssets.length} images.`);
}
console.log(JSON.stringify({ verified: true, articles: importedArticles.length, images: importedAssets.length }));
