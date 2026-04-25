/**
 * 成就系统。
 * 触发点只负责调用 checkAchievements;这里统一读取当前数据并补齐新解锁项。
 */
import { store } from "./store.js";

export const ACHIEVEMENTS = [
  { id: "streak_3", title: "三日有声", desc: "连续 3 天有学习记录", group: "习惯" },
  { id: "streak_7", title: "一周不掉线", desc: "连续 7 天有学习记录", group: "习惯" },
  { id: "streak_30", title: "月度长跑", desc: "连续 30 天有学习记录", group: "习惯" },
  { id: "learned_100", title: "百词启程", desc: "累计学习 100 个词", group: "词汇" },
  { id: "learned_500", title: "五百词仓", desc: "累计学习 500 个词", group: "词汇" },
  { id: "learned_1000", title: "千词入库", desc: "累计学习 1000 个词", group: "词汇" },
  { id: "mastered_100", title: "掌握百词", desc: "100 个词达到掌握或永久", group: "词汇" },
  { id: "wrongbook_clear", title: "错题清仓", desc: "学过至少 50 词且错题本清空", group: "复习" },
  { id: "perfect_session", title: "一场全对", desc: "单场至少 10 题且正确率 100%", group: "技巧" },
  { id: "dictation_perfect", title: "听写满分", desc: "听写单场至少 5 题且全对", group: "技巧" },
  { id: "boss_3star", title: "Boss 终结者", desc: "任意 Boss 关首次 3 星", group: "地图" },
  { id: "chapter_complete", title: "章节扫清", desc: "任意章节全部普通节点通关", group: "地图" },
  { id: "chapter_all_3star", title: "满星章节", desc: "任意章节全部普通节点 3 星", group: "地图" },
  { id: "tier_silver", title: "白银初登", desc: "段位积分首次达到白银", group: "段位" },
  { id: "tier_gold", title: "黄金门票", desc: "段位积分首次达到黄金", group: "段位" },
  { id: "tier_diamond", title: "钻石锋芒", desc: "段位积分首次达到钻石", group: "段位" },
  { id: "tier_king", title: "王者坐标", desc: "段位积分首次达到王者", group: "段位" },
  { id: "rank_win_10", title: "十胜在手", desc: "段位赛累计获胜 10 场", group: "段位" },
];

const TIER_POINTS = {
  silver: 120,
  gold: 240,
  diamond: 480,
  king: 600,
};

export async function checkAchievements(event = "manual", payload = {}) {
  try {
    const unlockedRows = await store.all("achievements");
    const unlocked = new Set(unlockedRows.map((row) => row.id));
    const snapshot = await buildSnapshot(payload);
    const fresh = [];

    for (const achievement of ACHIEVEMENTS) {
      if (unlocked.has(achievement.id)) continue;
      if (!isReached(achievement.id, snapshot)) continue;
      const row = { id: achievement.id, unlockedAt: Date.now(), event };
      await store.put("achievements", row);
      unlocked.add(achievement.id);
      fresh.push({ ...achievement, ...row });
    }

    return fresh;
  } catch (err) {
    console.warn("checkAchievements failed", err);
    return [];
  }
}

async function buildSnapshot(payload) {
  const [statsRows, progressRows, wrongRows, mapRows, rank] = await Promise.all([
    store.all("stats"),
    store.all("progress"),
    store.all("wrongbook"),
    store.all("mapProgress"),
    store.getSetting("rank", null),
  ]);

  const learned = progressRows.length;
  const mastered = progressRows.filter((p) => Number(p.box || 0) >= 3).length;
  const streak = currentStreak(statsRows);
  const map = await mapSnapshot(mapRows);

  return {
    payload,
    learned,
    mastered,
    wrongCount: wrongRows.length,
    streak,
    rank: rank || {},
    map,
  };
}

function isReached(id, s) {
  if (id === "streak_3") return s.streak >= 3;
  if (id === "streak_7") return s.streak >= 7;
  if (id === "streak_30") return s.streak >= 30;
  if (id === "learned_100") return s.learned >= 100;
  if (id === "learned_500") return s.learned >= 500;
  if (id === "learned_1000") return s.learned >= 1000;
  if (id === "mastered_100") return s.mastered >= 100;
  if (id === "wrongbook_clear") return s.learned >= 50 && s.wrongCount === 0;
  if (id === "perfect_session") return sessionPerfect(s.payload, 10);
  if (id === "dictation_perfect") return sessionPerfect(s.payload, 5) && /听写/.test(s.payload.summary?.mode || "");
  if (id === "boss_3star") return s.payload.node?.type === "boss" && Number(s.payload.stars || 0) >= 3;
  if (id === "chapter_complete") return s.map.anyComplete;
  if (id === "chapter_all_3star") return s.map.anyAllThree;
  if (id === "tier_silver") return Number(s.rank.highest || 0) >= TIER_POINTS.silver;
  if (id === "tier_gold") return Number(s.rank.highest || 0) >= TIER_POINTS.gold;
  if (id === "tier_diamond") return Number(s.rank.highest || 0) >= TIER_POINTS.diamond;
  if (id === "tier_king") return Number(s.rank.highest || 0) >= TIER_POINTS.king;
  if (id === "rank_win_10") return Number(s.rank.wins || 0) >= 10;
  return false;
}

function sessionPerfect(payload, minTotal) {
  const summary = payload.summary;
  return summary && Number(summary.total || 0) >= minTotal && Number(summary.accuracy || 0) >= 1;
}

function currentStreak(rows) {
  const active = new Set(rows.filter((r) => Number(r.total || 0) > 0).map((r) => r.date));
  let streak = 0;
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  while (active.has(d.toISOString().slice(0, 10))) {
    streak += 1;
    d.setDate(d.getDate() - 1);
  }
  return streak;
}

async function mapSnapshot(mapRows) {
  const progress = new Map(mapRows.map((row) => [row.nodeKey, row]));
  let anyComplete = false;
  let anyAllThree = false;

  try {
    const indexRes = await fetch("data/maps/index.json");
    if (!indexRes.ok) return { anyComplete, anyAllThree };
    const index = await indexRes.json();

    for (const meta of index.chapters || []) {
      const res = await fetch(`data/maps/${meta.file}`);
      if (!res.ok) continue;
      const chapter = await res.json();
      const nodes = (chapter.nodes || []).filter((node) => node.type !== "hidden");
      if (!nodes.length) continue;
      const stars = nodes.map((node) => {
        const row = progress.get(`${chapter.id}:${node.id}`);
        return Number(row?.bestStars || 0);
      });
      if (stars.every((n) => n > 0)) anyComplete = true;
      if (stars.every((n) => n >= 3)) anyAllThree = true;
    }
  } catch {
    return { anyComplete, anyAllThree };
  }

  return { anyComplete, anyAllThree };
}
