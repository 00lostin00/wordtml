/**
 * 真题加载器:从 data/exams/ 读取索引和单卷。
 */
const BASE = "data/exams";
let indexCache = null;
const examCache = new Map();

export async function getExamIndex() {
  if (indexCache) return indexCache;
  const res = await fetch(`${BASE}/index.json`);
  if (!res.ok) throw new Error(`真题索引加载失败:${res.status}`);
  indexCache = await res.json();
  return indexCache;
}

export async function loadExam(id) {
  if (examCache.has(id)) return examCache.get(id);
  const idx = await getExamIndex();
  const entry = (idx.exams || []).find((e) => e.id === id);
  if (!entry) throw new Error(`未知真题 id:${id}`);
  const res = await fetch(`${BASE}/${entry.file}`);
  if (!res.ok) throw new Error(`真题加载失败 ${entry.file}:${res.status}`);
  const data = await res.json();
  examCache.set(id, data);
  return data;
}

export function clearExamCache() {
  examCache.clear();
  indexCache = null;
}

/**
 * 把卷子按年份分组(新→旧),用于列表页展示。
 */
export function groupByYear(exams) {
  const groups = new Map();
  for (const e of exams) {
    const y = e.year || 0;
    if (!groups.has(y)) groups.set(y, []);
    groups.get(y).push(e);
  }
  // 年份新→旧
  const sortedYears = [...groups.keys()].sort((a, b) => b - a);
  return sortedYears.map((y) => ({
    year: y,
    exams: groups.get(y).sort((a, b) =>
      (b.month || 0) - (a.month || 0) || (a.set || 0) - (b.set || 0)
    ),
  }));
}

export const LABEL_INFO = {
  "complete":      { text: "完整",   color: "var(--ok)",     playable: true },
  "near-complete": { text: "近完整", color: "var(--accent)", playable: true },
  "partial":       { text: "部分",   color: "var(--warn)",   playable: false },
  "paper-only":    { text: "残缺",   color: "var(--fg-faint)", playable: false },
};

export function hasObjectiveAnswers(exam) {
  return Number(exam?.objectiveScorable || 0) > 0;
}

export function isExamPlayable(exam) {
  const labelPlayable = LABEL_INFO[exam?.label]?.playable;
  return Boolean(labelPlayable || exam?.objectiveReady || hasObjectiveAnswers(exam));
}

export function examStatusInfo(exam) {
  const info = LABEL_INFO[exam?.label] || LABEL_INFO["paper-only"];
  if (isExamPlayable(exam) && !info.playable) {
    return { ...info, text: "客观题可做", color: "var(--accent)", playable: true };
  }
  return info;
}
