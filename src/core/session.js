/**
 * 学习会话管理。
 *
 * 职责:
 *   - 组织一批待练词(调 srs.pickTodayBatch)
 *   - 调 Mode 渲染每道题
 *   - 收答题结果,喂回 SRS,更新进度 / 错题本 / 统计
 *   - 会话结束后回调汇总
 */
import { store } from "./store.js";
import { newProgress, grade } from "./srs.js";
import { normalizeEconomy } from "./items.js";

export class Session {
  /**
   * @param {object} cfg
   *   - words        Array<WordItem>  待练词
   *   - mode         Mode 对象
   *   - wordlistId   string
   *   - onFinish(summary)  完成回调
   */
  constructor(cfg) {
    this.words = cfg.words;
    this.mode = cfg.mode;
    this.wordlistId = cfg.wordlistId;
    this.onFinish = cfg.onFinish || (() => {});
    this.timeLimit = cfg.timeLimit || 0; // 秒,0 表示无限
    this.onTick = cfg.onTick || null;    // (remainMs) => void
    this.onEconomyChange = cfg.onEconomyChange || null;
    this.economy = normalizeEconomy(cfg.economy);
    this.timeBonusMs = 0;
    this.skipped = 0;
    this.cursor = 0;
    this.results = [];
    this.startedAt = Date.now();
    this.timedOut = false;
    this._timer = null;
  }

  get total() {
    return this.words.length;
  }

  get done() {
    return this.cursor;
  }

  get current() {
    return this.words[this.cursor];
  }

  /**
   * 渲染当前题到 host 元素。Mode 收到 onAnswer 回调,回调里吃评分。
   */
  renderCurrent(host) {
    host.innerHTML = "";
    if (this.cursor >= this.words.length || this.timedOut) {
      this.#finish();
      return;
    }
    this.#ensureTimer();
    const ctx = {
      word: this.current,
      pool: this.words,
      index: this.cursor,
      total: this.total,
      items: this.economy.items,
      hasTimer: !!this.timeLimit,
      useItem: (kind) => this.#useItem(kind, host),
      onAnswer: (result) => this.#submitAnswer(result, host),
    };
    const node = this.mode.render(ctx);
    host.appendChild(node);
  }

  #ensureTimer() {
    if (!this.timeLimit || this._timer) return;
    const tick = () => {
      const remainMs = this.timeLimit * 1000 + this.timeBonusMs - (Date.now() - this.startedAt);
      if (this.onTick) this.onTick(remainMs);
      if (remainMs <= 0) {
        clearInterval(this._timer);
        this._timer = null;
        this.timedOut = true;
        // 把所有剩余词标记为错,然后结算
        this.#finish();
      }
    };
    this._timer = setInterval(tick, 200);
    tick();
  }

  async #submitAnswer(result, host) {
    // result: { correct: boolean, quality?: 0..5, responseMs?: number }
    const quality = typeof result.quality === "number"
      ? result.quality
      : (result.correct ? 4 : 1);

    const word = this.current;
    const existing = await store.get("progress", word.id);
    const prev = existing || newProgress(word.id, this.wordlistId);
    const next = grade(prev, quality);
    await store.put("progress", next);

    // 错题本
    if (!result.correct) {
      const wb = (await store.get("wrongbook", word.id)) || {
        wordId: word.id,
        wordlistId: this.wordlistId,
        count: 0,
        lastWrong: 0,
        resolvedStreak: 0,
      };
      wb.count += 1;
      wb.lastWrong = Date.now();
      wb.resolvedStreak = 0;
      await store.put("wrongbook", wb);
    } else {
      const wb = await store.get("wrongbook", word.id);
      if (wb) {
        wb.resolvedStreak = (wb.resolvedStreak || 0) + 1;
        if (wb.resolvedStreak >= 3) {
          await store.delete("wrongbook", word.id);
        } else {
          await store.put("wrongbook", wb);
        }
      }
    }

    this.results.push({
      wordId: word.id,
      correct: result.correct,
      quality,
      responseMs: result.responseMs || 0,
      wasNew: !existing,
    });

    // 统计
    const statsPatch = { total: 1, correct: result.correct ? 1 : 0 };
    if (!existing) statsPatch.learned = 1;
    else statsPatch.reviewed = 1;
    await store.bumpStats(statsPatch);

    this.cursor += 1;
    this.renderCurrent(host);
  }

  async #useItem(kind, host) {
    const eco = normalizeEconomy(await store.getEconomy());
    const count = Number(eco.items[kind] || 0);
    if (count <= 0) {
      this.economy = eco;
      return { ok: false, message: "库存不足", economy: eco };
    }
    if (kind === "extend" && !this.timeLimit) {
      this.economy = eco;
      return { ok: false, message: "当前不是限时关卡", economy: eco };
    }

    eco.items[kind] = count - 1;
    await store.setEconomy(eco);
    this.economy = eco;
    if (this.onEconomyChange) this.onEconomyChange(eco);

    if (kind === "extend") {
      this.timeBonusMs += 30000;
      return { ok: true, message: "已延长 30 秒", economy: eco };
    }
    if (kind === "skip") {
      this.skipped += 1;
      this.cursor += 1;
      this.renderCurrent(host);
      return { ok: true, message: "已跳过本题", economy: eco };
    }

    return { ok: true, message: "道具已使用", economy: eco };
  }

  async #finish() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    const endedAt = Date.now();
    const correct = this.results.filter((r) => r.correct).length;
    // 限时模式:没答完的题算错,但主动跳过的题不计入本场总题数。
    const denom = this.timeLimit ? Math.max(0, this.words.length - this.skipped) : this.results.length;
    const summary = {
      startedAt: this.startedAt,
      endedAt,
      mode: this.mode.name,
      wordlistId: this.wordlistId,
      total: denom,
      answered: this.results.length,
      correct,
      accuracy: denom ? correct / denom : 0,
      durationMs: endedAt - this.startedAt,
      timedOut: this.timedOut,
      skipped: this.skipped,
      results: this.results,
    };
    await store.put("sessions", {
      startedAt: summary.startedAt,
      endedAt: summary.endedAt,
      mode: summary.mode,
      wordlistId: summary.wordlistId,
      total: summary.total,
      correct: summary.correct,
      skipped: summary.skipped,
    });
    this.onFinish(summary);
  }
}
