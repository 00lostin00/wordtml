/**
 * 快速反应。
 * 用现有混合玩法 + Session timeLimit 做 30/60/90 秒限时连答。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadWordlist } from "../core/wordlist.js";
import { pickTodayBatch } from "../core/srs.js";
import { makeMixedMode } from "../modes/mixed.js";
import { Session } from "../core/session.js";

const DURATIONS = [30, 60, 90];
const MODE_IDS = ["choice-en", "choice-cn", "spelling"];

export async function render(ctx) {
  const { host, router, query } = ctx;
  const seconds = Number(query.seconds || 0);
  if (!DURATIONS.includes(seconds)) {
    renderLanding(host, router);
    return;
  }
  await runRapid(host, router, seconds);
}

function renderLanding(host, router) {
  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("h2", { style: "margin:0" }, "⚡ 快速反应"),
      el("div", { class: "label", style: "margin-top:4px" }, "限时混合题,尽量多答对"),
    ]),
    el("button", { class: "ghost", onClick: () => router.go("/") }, "返回首页"),
  ]));

  host.appendChild(el("div", { class: "grid cols-3" }, DURATIONS.map((seconds) =>
    el("div", {
      class: "rapid-card",
      onClick: () => router.go("/rapid", { seconds }),
    }, [
      el("div", { class: "label" }, "限时挑战"),
      el("div", { class: "rapid-time" }, `${seconds}s`),
      el("div", { class: "sub" }, modeName(seconds)),
      el("button", { class: seconds === 60 ? "primary" : "" }, "开始"),
    ])
  )));

  host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "section-title" }, "规则"),
    el("ul", { class: "rule-list" }, [
      el("li", {}, "题型会在英译中、中译英、拼写之间随机切换。"),
      el("li", {}, "超时后未答完的题会计入本场总题数,跳过题不计入总数。"),
      el("li", {}, "限时挑战可使用延时道具,其他道具沿用基础玩法规则。"),
    ]),
  ]));
}

async function runRapid(host, router, seconds) {
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
  let words = pickTodayBatch(wordlist.words, progressMap, { newCount: 40, reviewCap: 80 });
  if (words.length < 15) words = fallbackWords(wordlist.words, 80);

  const mode = makeMixedMode(MODE_IDS, `${seconds} 秒快速反应`);
  const timerPill = el("span", { class: "pill" }, `⏱ ${seconds}s`);

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("button", { class: "ghost", onClick: () => router.go("/rapid") }, "← 退出"),
    el("div", { style: "text-align:center" }, [
      el("div", { style: "font-weight:700; font-size:18px" }, mode.name),
      el("div", { class: "label" }, `${words.length} 词池 · 混合题型`),
    ]),
    timerPill,
  ]));

  const modeHost = el("div", {});
  host.appendChild(modeHost);

  const economy = await store.getEconomy();
  const session = new Session({
    words,
    mode,
    wordlistId: activeId,
    economy,
    timeLimit: seconds,
    onTick: (remainMs) => {
      const left = Math.max(0, Math.ceil(remainMs / 1000));
      timerPill.textContent = `⏱ ${left}s`;
      timerPill.className = "pill" + (left <= 10 ? " err" : left <= 20 ? " warn" : "");
    },
    onFinish: (summary) => renderResult(modeHost, router, seconds, summary),
  });
  session.renderCurrent(modeHost);
}

function renderResult(host, router, seconds, summary) {
  host.innerHTML = "";
  const acc = summary.total ? Math.round(summary.accuracy * 100) : 0;
  const speed = summary.durationMs ? (summary.answered / (summary.durationMs / 1000)).toFixed(1) : "0.0";
  host.appendChild(el("div", { class: "card", style: "text-align:center" }, [
    el("h2", { style: "margin:0" }, "⚡ 挑战结束"),
    el("div", { class: "grid cols-4", style: "margin:20px 0" }, [
      stat("时长", `${seconds}s`, summary.timedOut ? "时间到" : "提前完成"),
      stat("作答", summary.answered, "题"),
      stat("正确率", `${acc}%`, `${summary.correct}/${summary.total}`),
      stat("速度", speed, "题/秒"),
    ]),
    el("div", { class: "row", style: "justify-content:center; gap:8px" }, [
      el("button", { class: "ghost", onClick: () => router.go("/rapid") }, "换时长"),
      el("button", { class: "primary", onClick: () => router.go("/rapid", { seconds }) }, "再来一轮"),
    ]),
  ]));
}

function fallbackWords(words, count) {
  return [...words].sort(() => Math.random() - 0.5).slice(0, Math.min(count, words.length));
}

function modeName(seconds) {
  if (seconds === 30) return "短冲刺";
  if (seconds === 60) return "标准局";
  return "耐力局";
}

function stat(label, value, sub) {
  return el("div", { class: "stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, String(value)),
    el("div", { class: "sub" }, sub),
  ]);
}
