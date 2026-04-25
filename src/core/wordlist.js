/**
 * 词表加载器:从 data/wordlists/ 目录抓 JSON,做一层缓存。
 */
const cache = new Map();
let indexCache = null;

const BASE = "data/wordlists";

export async function getIndex() {
  if (indexCache) return indexCache;
  const res = await fetch(`${BASE}/index.json`);
  if (!res.ok) throw new Error(`加载词表索引失败: ${res.status}`);
  indexCache = await res.json();
  return indexCache;
}

export async function loadWordlist(id) {
  if (cache.has(id)) return cache.get(id);

  const index = await getIndex();
  const entry = index.wordlists.find((w) => w.id === id);
  if (!entry) throw new Error(`未知词表 id: ${id}`);

  const res = await fetch(`${BASE}/${entry.file}`);
  if (!res.ok) throw new Error(`加载词表失败 ${entry.file}: ${res.status}`);
  const data = await res.json();

  // 简单校验
  if (!data.meta || !Array.isArray(data.words)) {
    throw new Error(`词表格式非法: ${entry.file}`);
  }

  cache.set(id, data);
  return data;
}

export function clearCache() {
  cache.clear();
  indexCache = null;
}
