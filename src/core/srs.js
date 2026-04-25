/**
 * SRS(间隔重复)引擎 —— 简化 SM-2。
 *
 * 质量打分 quality ∈ [0, 5]:
 *   5 完美  4 正确(轻松)  3 正确(勉强)
 *   2 错误(大概记得)  1 错误(面熟)  0 完全不认识
 *
 * 状态机熟练度分档 box:
 *   0 陌生 → 1 学习中 → 2 熟悉 → 3 掌握 → 4 永久
 *
 * 间隔(天)按 box 映射:0d / 1d / 3d / 7d / 21d / 60d
 */
const DAY = 24 * 60 * 60 * 1000;

const BOX_INTERVALS_DAYS = [0, 1, 3, 7, 21, 60];
export const BOX_LABELS = ["陌生", "学习中", "熟悉", "掌握", "永久"];

export function newProgress(wordId, wordlistId, now = Date.now()) {
  return {
    wordId,
    wordlistId,
    box: 0,
    ease: 2.5,
    reps: 0,
    interval: 0,
    due: now,
    wrong: 0,
    lastReviewed: 0,
  };
}

/**
 * 评分 → 新状态
 * @param {object} progress 旧进度
 * @param {number} quality  0..5
 * @param {number} now
 * @returns {object} 新进度
 */
export function grade(progress, quality, now = Date.now()) {
  const p = { ...progress };
  p.reps += 1;
  p.lastReviewed = now;

  const correct = quality >= 3;
  if (!correct) {
    p.wrong += 1;
    p.box = 0;
    p.interval = 0;
    p.due = now + 10 * 60 * 1000; // 10 分钟后再来
  } else {
    p.box = Math.min(BOX_INTERVALS_DAYS.length - 1, p.box + 1);
    const days = BOX_INTERVALS_DAYS[p.box] || 0;
    p.interval = days;
    p.due = now + days * DAY;
  }

  // 难度因子(备用,后续可用于更精细的调度)
  const ef = p.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
  p.ease = Math.max(1.3, ef);

  return p;
}

export function isDue(progress, now = Date.now()) {
  return !progress || progress.due <= now;
}

export function boxLabel(box) {
  return BOX_LABELS[box] || "—";
}

/**
 * 从全部词里挑出今天要练的一批。
 *
 * 优先级:
 *   1. 已到期的复习(progress.due <= now)
 *   2. 新词(无 progress)
 *
 * @param {Array} allWords       完整词表
 * @param {Map} progressMap      wordId → progress(可能不全)
 * @param {object} opts
 *   - newCount   今日新词目标
 *   - reviewCap  复习数上限
 * @returns {Array} 排好序的 word 数组
 */
export function pickTodayBatch(allWords, progressMap, opts = {}) {
  const { newCount = 20, reviewCap = 100 } = opts;
  const now = Date.now();

  const dueReview = [];
  const fresh = [];

  for (const w of allWords) {
    const p = progressMap.get(w.id);
    if (!p) {
      fresh.push(w);
    } else if (p.due <= now && p.box < BOX_INTERVALS_DAYS.length - 1) {
      dueReview.push({ w, p });
    }
  }

  // 到期复习先按 due 排序(越早越优先)
  dueReview.sort((a, b) => a.p.due - b.p.due);

  const batch = [];
  for (let i = 0; i < Math.min(reviewCap, dueReview.length); i++) batch.push(dueReview[i].w);
  for (let i = 0; i < Math.min(newCount, fresh.length); i++) batch.push(fresh[i]);

  // 新词 + 复习随机洗牌,防止"先全新后全旧"
  for (let i = batch.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [batch[i], batch[j]] = [batch[j], batch[i]];
  }

  return batch;
}
