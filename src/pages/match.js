/**
 * 连连看。
 * 独立页面,一次展示 10 个英文和 10 个中文释义,点击两侧完成配对。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadWordlist } from "../core/wordlist.js";
import { pickTodayBatch } from "../core/srs.js";
import { newProgress, grade } from "../core/srs.js";
import { checkAchievements } from "../core/achievements.js";

const PAIR_COUNT = 10;

export async function render(ctx) {
  const { host, router } = ctx;
  const activeId = await store.getSetting("activeWordlist", "cet6");

  let wordlist;
  try {
    wordlist = await loadWordlist(activeId);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "词表加载失败"),
      el("div", { class: "feedback err" }, e.message),
      el("button", { class: "primary", onClick: () => router.go("/settings") }, "去设置"),
    ]));
    return;
  }

  const progressRows = await store.all("progress");
  const progressMap = new Map(progressRows.filter((p) => p.wordlistId === activeId).map((p) => [p.wordId, p]));
  let words = pickTodayBatch(wordlist.words, progressMap, { newCount: PAIR_COUNT, reviewCap: PAIR_COUNT });
  if (words.length < PAIR_COUNT) words = fallbackWords(wordlist.words, PAIR_COUNT);

  runMatch(host, router, activeId, words);
}

function runMatch(host, router, wordlistId, words) {
  const startedAt = Date.now();
  const left = shuffle(words.map((word) => ({ id: word.id, text: word.word })));
  const right = shuffle(words.map((word) => ({ id: word.id, text: firstDef(word) })));
  const state = {
    leftId: "",
    rightId: "",
    done: new Set(),
    wrong: new Set(),
    attempts: 0,
    correct: 0,
  };

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("h2", { style: "margin:0" }, "🔗 连连看"),
      el("div", { class: "label", style: "margin-top:4px" }, "点击左侧英文和右侧释义完成配对"),
    ]),
    el("button", { class: "ghost", onClick: () => router.go("/") }, "返回首页"),
  ]));

  const status = el("span", { class: "pill" }, "");
  const board = el("div", { class: "match-board" });
  const lines = svgEl("svg", { class: "match-lines", viewBox: "0 0 100 100", preserveAspectRatio: "none" });
  const resultHost = el("div");
  const leftNodes = new Map();
  const rightNodes = new Map();

  host.appendChild(el("div", { class: "card" }, [
    el("div", { class: "row between", style: "margin-bottom:14px" }, [
      status,
      el("button", { class: "ghost", onClick: () => router.go("/match") }, "换一组"),
    ]),
    el("div", { class: "match-wrap" }, [lines, board]),
  ]));
  host.appendChild(resultHost);

  const refresh = () => {
    status.textContent = `已配对 ${state.done.size}/${words.length} · 尝试 ${state.attempts}`;
    board.innerHTML = "";
    leftNodes.clear();
    rightNodes.clear();
    board.appendChild(renderColumn(left, "left"));
    board.appendChild(renderColumn(right, "right"));
    requestAnimationFrame(drawLines);
  };

  const choose = async (side, id) => {
    if (state.done.has(id)) return;
    if (side === "left") state.leftId = state.leftId === id ? "" : id;
    if (side === "right") state.rightId = state.rightId === id ? "" : id;

    if (state.leftId && state.rightId) {
      state.attempts += 1;
      if (state.leftId === state.rightId) {
        state.done.add(state.leftId);
        state.correct += 1;
      } else {
        state.wrong.add(state.leftId);
        state.wrong.add(state.rightId);
      }
      state.leftId = "";
      state.rightId = "";
    }

    refresh();
    if (state.done.size >= words.length) {
      await finishMatch(resultHost, router, wordlistId, words, state, startedAt);
    }
  };

  function renderColumn(items, side) {
    return el("div", { class: "match-column" }, items.map((item) => {
      const active = side === "left" ? state.leftId === item.id : state.rightId === item.id;
      const done = state.done.has(item.id);
      const tile = el("button", {
        class: "match-tile" + (active ? " active" : "") + (done ? " done" : ""),
        disabled: done,
        onClick: () => choose(side, item.id),
      }, item.text);
      if (side === "left") leftNodes.set(item.id, tile);
      else rightNodes.set(item.id, tile);
      return tile;
    }));
  }

  function drawLines() {
    lines.innerHTML = "";
    const wrapRect = board.getBoundingClientRect();
    if (!wrapRect.width || !wrapRect.height) return;

    for (const id of state.done) {
      const from = leftNodes.get(id);
      const to = rightNodes.get(id);
      if (!from || !to) continue;
      const a = from.getBoundingClientRect();
      const b = to.getBoundingClientRect();
      const x1 = ((a.right - wrapRect.left) / wrapRect.width) * 100;
      const y1 = ((a.top + a.height / 2 - wrapRect.top) / wrapRect.height) * 100;
      const x2 = ((b.left - wrapRect.left) / wrapRect.width) * 100;
      const y2 = ((b.top + b.height / 2 - wrapRect.top) / wrapRect.height) * 100;
      lines.appendChild(svgEl("line", {
        x1, y1, x2, y2,
        class: "match-line",
      }));
    }
  }

  refresh();
}

async function finishMatch(host, router, wordlistId, words, state, startedAt) {
  const endedAt = Date.now();
  const wrongIds = state.wrong;
  let correct = 0;
  let learned = 0;

  for (const word of words) {
    const isCorrect = !wrongIds.has(word.id);
    if (isCorrect) correct += 1;
    const existing = await store.get("progress", word.id);
    if (!existing) learned += 1;
    const prev = existing || newProgress(word.id, wordlistId);
    await store.put("progress", grade(prev, isCorrect ? 5 : 2));
    if (!isCorrect) await bumpWrong(word.id, wordlistId);
  }

  await store.bumpStats({
    total: words.length,
    correct,
    learned,
    reviewed: words.length - learned,
  });

  const summary = {
    startedAt,
    endedAt,
    mode: "连连看",
    wordlistId,
    total: words.length,
    answered: words.length,
    correct,
    accuracy: words.length ? correct / words.length : 0,
    durationMs: endedAt - startedAt,
    timedOut: false,
    skipped: 0,
    results: words.map((word) => ({ wordId: word.id, correct: !wrongIds.has(word.id) })),
  };
  await store.put("sessions", {
    startedAt,
    endedAt,
    mode: summary.mode,
    wordlistId,
    total: summary.total,
    correct: summary.correct,
    skipped: 0,
  });
  await checkAchievements("session", { summary });

  const acc = Math.round(summary.accuracy * 100);
  host.innerHTML = "";
  host.appendChild(el("div", { class: "card", style: "margin-top:16px; text-align:center" }, [
    el("h2", { style: "margin:0" }, "✅ 配对完成"),
    el("div", { class: "grid cols-3", style: "margin:20px 0" }, [
      stat("正确", `${correct}/${words.length}`, `${acc}%`),
      stat("尝试", state.attempts, "次"),
      stat("用时", formatDuration(summary.durationMs), "本轮"),
    ]),
    el("div", { class: "row", style: "justify-content:center" }, [
      el("button", { class: "ghost", onClick: () => router.go("/") }, "回首页"),
      el("button", { class: "primary", onClick: () => router.go("/match") }, "再来一组"),
    ]),
  ]));
}

async function bumpWrong(wordId, wordlistId) {
  const wb = (await store.get("wrongbook", wordId)) || {
    wordId,
    wordlistId,
    count: 0,
    lastWrong: 0,
    resolvedStreak: 0,
  };
  wb.count += 1;
  wb.lastWrong = Date.now();
  wb.resolvedStreak = 0;
  await store.put("wrongbook", wb);
}

function fallbackWords(words, count) {
  return shuffle(words).slice(0, Math.min(count, words.length));
}

function shuffle(items) {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function firstDef(word) {
  return (word.defs_cn || []).slice(0, 2).join("；") || word.word;
}

function stat(label, value, sub) {
  return el("div", { class: "stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, String(value)),
    el("div", { class: "sub" }, sub),
  ]);
}

function formatDuration(ms) {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m${s % 60}s`;
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}
