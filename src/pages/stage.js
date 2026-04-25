/**
 * 关卡运行页。/stage?chapter=xxx&node=yyy
 *
 * 加载章节/词表/节点 → 选词 → 选玩法(单模式或混合) → 开 Session(可带 timeLimit)
 * → 结束后评星 + 落进度 + 给金币。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadChapter, sliceNodeWords, recordNodeResult } from "../core/map-engine.js";
import { loadWordlist } from "../core/wordlist.js";
import { getMode } from "../modes/_interface.js";
import { makeMixedMode } from "../modes/mixed.js";
import { Session } from "../core/session.js";

export async function render(ctx) {
  const { host, router, query } = ctx;
  const { chapter: chapterId, node: nodeId } = query;

  if (!chapterId || !nodeId) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "参数缺失"),
      el("button", { class: "primary", onClick: () => router.go("/map") }, "回地图"),
    ]));
    return;
  }

  let chapter, wordlist, node;
  try {
    chapter = await loadChapter(chapterId);
    node = chapter.nodes.find((n) => n.id === nodeId);
    if (!node) throw new Error(`节点 ${nodeId} 不存在`);
    wordlist = await loadWordlist(chapter.wordlistId);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "加载失败"),
      el("div", { class: "feedback err" }, e.message),
      el("button", { class: "primary", onClick: () => router.go("/map") }, "回地图"),
    ]));
    return;
  }

  await runStage(host, router, chapter, node, wordlist);
}

async function runStage(host, router, chapter, node, wordlist) {
  // 宝箱关特殊:从错题本里取词
  let words;
  if (node.type === "treasure" || node.mode === "review") {
    const wordMap = new Map(wordlist.words.map((w) => [w.id, w]));
    const wrong = (await store.all("wrongbook")).filter(
      (w) => w.wordlistId === chapter.wordlistId && wordMap.has(w.wordId)
    );
    words = wrong
      .sort((a, b) => b.count - a.count)
      .slice(0, node.count || 10)
      .map((w) => wordMap.get(w.wordId));
    if (words.length === 0) {
      renderNoWrongWords(host, router, chapter, node);
      return;
    }
  } else {
    words = sliceNodeWords(chapter, wordlist, node);
  }

  // 选玩法
  let mode;
  if (node.type === "treasure") {
    mode = getMode("choice-en"); // 宝箱关默认用选择题,简单点
  } else if (node.modes && node.modes.length > 1) {
    mode = makeMixedMode(node.modes, node.type === "boss" ? "Boss 混合" : "精英混合");
  } else {
    mode = getMode(node.mode || (node.modes && node.modes[0]));
  }
  if (!mode) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "玩法配置错误"),
      el("div", { class: "feedback err" }, `未知 mode: ${node.mode || node.modes}`),
    ]));
    return;
  }

  // 顶部信息栏
  const timerPill = el("span", { class: "pill" }, node.timeLimit ? `⏱ ${node.timeLimit}s` : "—");
  const header = el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("button", { class: "ghost", onClick: () => router.go("/map", { chapter: chapter.id }) }, "← 退出"),
    ]),
    el("div", { style: "text-align:center" }, [
      el("div", { style: "font-weight:600" }, `${typeBadge(node.type)} ${node.name}`),
      el("div", { class: "label" }, `${chapter.icon} ${chapter.name} · ${mode.name}`),
    ]),
    el("div", { class: "row", style: "gap:8px" }, [
      el("span", { class: "pill" }, `📝 ${words.length} 词`),
      timerPill,
    ]),
  ]);
  host.appendChild(header);

  const modeHost = el("div", {});
  host.appendChild(modeHost);

  const economy = await store.getEconomy();
  const session = new Session({
    words,
    mode,
    wordlistId: chapter.wordlistId,
    economy,
    timeLimit: node.timeLimit || 0,
    onTick: node.timeLimit ? (remainMs) => {
      const s = Math.max(0, Math.ceil(remainMs / 1000));
      timerPill.textContent = `⏱ ${s}s`;
      timerPill.className = "pill" + (s <= 10 ? " err" : s <= 30 ? " warn" : "");
    } : null,
    onFinish: async (summary) => {
      const result = await recordNodeResult(chapter.id, node, summary);
      renderResult(modeHost, router, chapter, node, summary, result);
    },
  });
  session.renderCurrent(modeHost);
}

function renderNoWrongWords(host, router, chapter, node) {
  host.appendChild(el("div", { class: "card" }, [
    el("h2", { style: "margin-top:0" }, `💎 ${node.name}`),
    el("div", { class: "empty" }, [
      el("div", { style: "font-size:40px" }, "📭"),
      el("div", { style: "margin-top:8px" }, "错题本空空,宝箱里没词可刷。"),
      el("div", { class: "label", style: "margin-top:4px" }, "先去其他节点多答错几题再来。"),
    ]),
    el("div", { class: "row end" }, [
      el("button", { class: "primary", onClick: () => router.go("/map", { chapter: chapter.id }) }, "回地图"),
    ]),
  ]));
}

function typeBadge(type) {
  return {
    normal: "🌿",
    elite: "⚔️",
    boss: "👹",
    treasure: "💎",
    hidden: "❓",
  }[type] || "🌿";
}

function renderResult(host, router, chapter, node, summary, result) {
  host.innerHTML = "";
  const stars = result.stars;
  const starStr = "⭐".repeat(stars) + "☆".repeat(3 - stars);
  const acc = Math.round(summary.accuracy * 100);
  const title = stars === 0
    ? "挑战失败"
    : stars === 3 ? "完美通关 🎉"
    : stars === 2 ? "顺利通关"
    : "勉强通关";

  host.appendChild(el("div", { class: "card", style: "text-align:center" }, [
    el("div", { style: "font-size:42px; letter-spacing:8px; margin-bottom:8px" }, starStr),
    el("h2", { style: "margin:0" }, title),
    el("div", { class: "grid cols-3", style: "margin:20px 0" }, [
      statLine("正确率", `${acc}%`, `${summary.correct}/${summary.total}`),
      statLine("用时", formatDuration(summary.durationMs),
        summary.timedOut ? "超时" : (node.timeLimit ? `限 ${node.timeLimit}s` : "不限时")),
      statLine("金币", `+${result.rewardedCoins || 0}`, result.rewardedCoins ? "升星奖励" : "无变化"),
    ]),
    el("div", { class: "row", style: "justify-content:center; gap:8px" }, [
      el("button", { class: "ghost", onClick: () => router.go("/map", { chapter: chapter.id }) }, "回地图"),
      el("button", { class: "primary", onClick: () => location.reload() }, "再挑战"),
    ]),
  ]));
}

function statLine(label, value, sub) {
  return el("div", { class: "stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, value),
    sub ? el("div", { class: "sub" }, sub) : null,
  ]);
}

function formatDuration(ms) {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m${s % 60}s`;
}
