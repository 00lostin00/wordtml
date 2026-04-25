/**
 * 段位赛引擎。
 *
 * 6 大段 × 3 小段 = 18 个台阶,用"积分阈值"驱动当前段位:
 *   - 胜 +20,连胜每场额外 +min(streak, 5)
 *   - 败 -15,但每日第一败有保护(不扣分,只重置连胜)
 *   - 每日挑战赢一次 +30(当日)
 *
 * 胜负判定:错词数 <= tier.maxWrong → 胜,否则败。超时同样算败。
 */
import { store } from "./store.js";
import { checkAchievements } from "./achievements.js";

const BIG_TIERS = [
  { big: "bronze",   label: "🥉 青铜", color: "#b87333" },
  { big: "silver",   label: "🥈 白银", color: "#c0c0c0" },
  { big: "gold",     label: "🥇 黄金", color: "#ffd700" },
  { big: "platinum", label: "💠 铂金", color: "#66e0d8" },
  { big: "diamond",  label: "💎 钻石", color: "#6ab0ff" },
  { big: "king",     label: "👑 王者", color: "#ff6adc" },
];

// 每大段的战斗参数(词量 / 时限 / 容错 / 用 cet6 前 N 个词)
export const TIER_PARAMS = {
  bronze:   { wordCount: 10, timeLimit: 120, maxWrong: 3, wordSliceEnd: 500,  modes: ["choice-en", "choice-cn"] },
  silver:   { wordCount: 15, timeLimit: 120, maxWrong: 3, wordSliceEnd: 1000, modes: ["choice-en", "choice-cn", "spelling"] },
  gold:     { wordCount: 20, timeLimit: 120, maxWrong: 2, wordSliceEnd: 2000, modes: ["choice-en", "choice-cn", "spelling"] },
  platinum: { wordCount: 25, timeLimit: 100, maxWrong: 2, wordSliceEnd: 3000, modes: ["choice-en", "spelling", "dictation"] },
  diamond:  { wordCount: 30, timeLimit: 90,  maxWrong: 1, wordSliceEnd: 4500, modes: ["choice-en", "choice-cn", "spelling", "dictation"] },
  king:     { wordCount: 30, timeLimit: 60,  maxWrong: 0, wordSliceEnd: Infinity, modes: ["choice-en", "choice-cn", "spelling", "dictation"] },
};

// 每小段跨度 = 40 积分
const STEP = 40;

const SUB_LABELS = { 3: "III", 2: "II", 1: "I" };

export const TIERS = (() => {
  const out = [];
  let idx = 0;
  for (const bt of BIG_TIERS) {
    for (const sub of [3, 2, 1]) {
      out.push({
        key: `${bt.big}-${sub}`,
        big: bt.big,
        bigLabel: bt.label,
        subLabel: SUB_LABELS[sub],
        label: `${bt.label} ${SUB_LABELS[sub]}`,
        color: bt.color,
        index: idx,
        minPoints: idx * STEP,
        maxPoints: (idx + 1) * STEP,
      });
      idx += 1;
    }
  }
  return out;
})();

export function tierByIndex(i) {
  return TIERS[Math.max(0, Math.min(TIERS.length - 1, i))];
}

export function tierByPoints(points) {
  const idx = Math.max(0, Math.min(TIERS.length - 1, Math.floor(points / STEP)));
  return TIERS[idx];
}

export async function getRankState() {
  const raw = await store.getSetting("rank", null);
  return raw || {
    points: 0,
    streak: 0,
    wins: 0,
    losses: 0,
    highest: 0,
    dailyDoneDate: "",
    lossProtectionDate: "",
  };
}

export async function setRankState(s) {
  return store.setSetting("rank", s);
}

/**
 * 根据本场 Session 汇总 + 选择的段位参数,算胜负与积分变化。
 */
export async function settleMatch({ tierKey, summary, isDaily }) {
  const tier = TIERS.find((t) => t.key === tierKey);
  if (!tier) throw new Error("未知 tier: " + tierKey);
  const params = TIER_PARAMS[tier.big];
  const wrong = summary.total - summary.correct;
  const win = !summary.timedOut && wrong <= params.maxWrong;

  const state = await getRankState();
  const todayStr = new Date().toISOString().slice(0, 10);

  let delta = 0;
  let note = "";
  if (win) {
    const bonus = Math.min(state.streak, 5);
    delta = 20 + bonus;
    state.streak += 1;
    state.wins += 1;
    if (isDaily && state.dailyDoneDate !== todayStr) {
      delta += 30;
      state.dailyDoneDate = todayStr;
      note = "每日挑战奖励 +30";
    }
  } else {
    const protectionAvail = state.lossProtectionDate !== todayStr;
    if (protectionAvail) {
      delta = 0;
      state.lossProtectionDate = todayStr;
      note = "每日首败保护,未扣分";
    } else {
      delta = -15;
    }
    state.streak = 0;
    state.losses += 1;
  }

  state.points = Math.max(0, state.points + delta);
  state.highest = Math.max(state.highest, state.points);
  await setRankState(state);
  await store.put("rankHistory", {
    at: Date.now(),
    tierKey: tier.key,
    points: state.points,
    highest: state.highest,
    delta,
    win,
    isDaily: !!isDaily,
  });
  const unlockedAchievements = await checkAchievements("rank", { tierKey, summary, win, delta, state });

  return {
    win,
    wrong,
    maxWrong: params.maxWrong,
    delta,
    note,
    newState: state,
    newTier: tierByPoints(state.points),
    unlockedAchievements,
  };
}

export function dailyChallengeDoneToday(state) {
  const todayStr = new Date().toISOString().slice(0, 10);
  return state.dailyDoneDate === todayStr;
}

/**
 * 从词表里切出对应段位的候选词池。
 */
export function poolForTier(tier, wordlist) {
  const params = TIER_PARAMS[tier.big];
  const end = params.wordSliceEnd === Infinity ? wordlist.words.length : Math.min(params.wordSliceEnd, wordlist.words.length);
  return wordlist.words.slice(0, end);
}

export function pickWordsForMatch(tier, wordlist) {
  const params = TIER_PARAMS[tier.big];
  const pool = poolForTier(tier, wordlist);
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, params.wordCount);
}
