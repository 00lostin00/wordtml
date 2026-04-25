/**
 * 地图引擎。
 *
 * 职责:
 *   - 加载章节配置 + 当前地图进度,算出每个节点的状态:locked / unlocked / cleared + 星数
 *   - 计算节点的星级结果
 *   - 从词表切出节点要用的词
 *
 * 节点类型:
 *   normal   单一玩法,10 词
 *   elite    两种玩法随机切换,15 词
 *   boss     四种玩法随机切换,20 词,限时(boss 才算通关)
 *   treasure 复习错题本
 *   hidden   所有前置 3 星才解锁
 *
 * 配置示例见 data/maps/cet6-forest.json。
 */
import { store } from "./store.js";
import { checkAchievements } from "./achievements.js";

const MAP_BASE = "data/maps";
let indexCache = null;
const chapterCache = new Map();

export async function getMapIndex() {
  if (indexCache) return indexCache;
  const res = await fetch(`${MAP_BASE}/index.json`);
  if (!res.ok) throw new Error(`加载地图索引失败:${res.status}`);
  indexCache = await res.json();
  return indexCache;
}

export async function loadChapter(id) {
  if (chapterCache.has(id)) return chapterCache.get(id);
  const idx = await getMapIndex();
  const entry = idx.chapters.find((c) => c.id === id);
  if (!entry) throw new Error(`未知章节:${id}`);
  const res = await fetch(`${MAP_BASE}/${entry.file}`);
  if (!res.ok) throw new Error(`加载章节失败 ${entry.file}:${res.status}`);
  const data = await res.json();
  chapterCache.set(id, data);
  return data;
}

export function nodeKey(chapterId, nodeId) {
  return `${chapterId}:${nodeId}`;
}

export async function getChapterProgress(chapterId) {
  const rows = await store.byIndex("mapProgress", "chapterId", chapterId);
  const m = new Map();
  for (const r of rows) m.set(r.nodeId, r);
  return m;
}

/**
 * 节点状态
 *   state: locked | unlocked | cleared
 *   stars: 0..3(最好成绩)
 */
export function nodeState(node, progressMap) {
  const row = progressMap.get(node.id);
  const stars = row ? row.bestStars || 0 : 0;
  const cleared = stars > 0;

  const requires = node.requires || [];
  let unlocked = true;
  for (const reqId of requires) {
    const rp = progressMap.get(reqId);
    if (!rp || (rp.bestStars || 0) === 0) {
      unlocked = false;
      break;
    }
  }

  // 隐藏节点:要求前置全 3 星才可见
  if (node.type === "hidden" && !cleared) {
    const allThreeStar = requires.every((reqId) => {
      const rp = progressMap.get(reqId);
      return rp && (rp.bestStars || 0) >= 3;
    });
    if (!allThreeStar) return { state: "hidden", stars: 0, visible: false };
  }

  return {
    state: cleared ? "cleared" : unlocked ? "unlocked" : "locked",
    stars,
    visible: true,
  };
}

/**
 * 给定章节配置,从词表切出节点要用的词。
 * @param {object} chapter    章节配置
 * @param {object} wordlist   完整词表
 * @param {object} node       节点
 */
export function sliceNodeWords(chapter, wordlist, node) {
  const [from, to] = chapter.wordRange || [0, wordlist.words.length];
  const excluded = new Set(chapter.excludeWordIds || []);
  const pool = wordlist.words
    .slice(from, Math.min(to, wordlist.words.length))
    .filter((word) => !excluded.has(word.id));
  const count = node.count || 10;
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count);
}

/**
 * 根据本次成绩算星数。
 *   ⭐   正确率 >= 60%
 *   ⭐⭐  正确率 >= 85%
 *   ⭐⭐⭐ 正确率 == 100% 且在限时内完成(无限时则只要 100% 即可)
 *
 * @param {object} summary   Session.onFinish 的汇总
 * @param {object} node      节点配置
 */
export function evaluateStars(summary, node) {
  const acc = summary.accuracy;
  if (acc < 0.6) return 0;

  const withinTime = node.timeLimit
    ? summary.durationMs <= node.timeLimit * 1000
    : true;

  if (acc >= 1 && withinTime) return 3;
  if (acc >= 0.85) return 2;
  return 1;
}

export async function recordNodeResult(chapterId, node, summary) {
  const key = nodeKey(chapterId, node.id);
  const prev = (await store.get("mapProgress", key)) || {
    nodeKey: key,
    chapterId,
    nodeId: node.id,
    bestStars: 0,
    bestAccuracy: 0,
    attempts: 0,
    firstClearedAt: 0,
    lastAttemptAt: 0,
  };

  const stars = evaluateStars(summary, node);
  const rewarded = stars > prev.bestStars ? starReward(stars) - starReward(prev.bestStars) : 0;

  prev.attempts += 1;
  prev.lastAttemptAt = Date.now();
  if (stars > prev.bestStars) {
    prev.bestStars = stars;
    prev.bestAccuracy = summary.accuracy;
    if (!prev.firstClearedAt) prev.firstClearedAt = Date.now();
  } else if (summary.accuracy > prev.bestAccuracy) {
    prev.bestAccuracy = summary.accuracy;
  }
  await store.put("mapProgress", prev);

  // 首次达到某星级给金币
  if (rewarded > 0) await store.addCoins(rewarded);
  const unlockedAchievements = await checkAchievements("map", { chapterId, node, stars, summary });

  return { stars, previousBest: prev.bestStars, rewardedCoins: rewarded, unlockedAchievements };
}

function starReward(stars) {
  // 累计奖励:1★=5、2★=15、3★=30
  return [0, 5, 15, 30][stars] || 0;
}

export function chapterCompletion(chapter, progressMap) {
  const nodes = chapter.nodes.filter((n) => n.type !== "hidden");
  let stars = 0;
  let cleared = 0;
  for (const n of nodes) {
    const p = progressMap.get(n.id);
    if (p && p.bestStars > 0) {
      cleared += 1;
      stars += p.bestStars;
    }
  }
  return {
    cleared,
    total: nodes.length,
    stars,
    maxStars: nodes.length * 3,
    percent: nodes.length ? cleared / nodes.length : 0,
  };
}
