/**
 * 复习页。两个池子:
 *   1. 到期复习 —— progress.due <= now
 *   2. 错题本   —— wrongbook 全量
 *
 * 选池子 + 选玩法 → 开一个 Session。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadWordlist } from "../core/wordlist.js";
import { listModes, getMode } from "../modes/_interface.js";
import { Session } from "../core/session.js";

export async function render(ctx) {
  const { host, router } = ctx;

  const activeId = await store.getSetting("activeWordlist", "cet6");
  let wordlist;
  try {
    wordlist = await loadWordlist(activeId);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "词表加载失败"),
      el("div", { class: "feedback err" }, String(e.message || e)),
      el("button", { class: "primary", onClick: () => router.go("/settings") }, "去设置"),
    ]));
    return;
  }

  const wordMap = new Map(wordlist.words.map((w) => [w.id, w]));
  const now = Date.now();

  const allProgress = (await store.all("progress")).filter((p) => p.wordlistId === activeId);
  const dueRows = allProgress.filter((p) => p.due <= now && wordMap.has(p.wordId));
  const dueWords = dueRows
    .sort((a, b) => a.due - b.due)
    .map((p) => wordMap.get(p.wordId))
    .filter(Boolean);

  const wrongRows = (await store.all("wrongbook")).filter(
    (w) => w.wordlistId === activeId && wordMap.has(w.wordId)
  );
  const wrongWords = wrongRows
    .sort((a, b) => b.count - a.count)
    .map((w) => wordMap.get(w.wordId))
    .filter(Boolean);

  const poolArea = el("div");
  host.appendChild(el("div", { class: "card" }, [
    el("h2", { style: "margin-top:0" }, "🔁 复习"),
    el("div", { class: "row" }, [
      el("span", { class: "pill" }, `词表:${wordlist.meta.name}`),
      el("span", { class: "pill" }, `到期 ${dueWords.length}`),
      el("span", { class: "pill" }, `错题 ${wrongWords.length}`),
    ]),
  ]));

  host.appendChild(el("div", { class: "grid cols-2", style: "margin-top:16px" }, [
    poolCard({
      title: "到期复习",
      desc: "已学词中到达复习时间的,优先级最高。",
      count: dueWords.length,
      emptyHint: "暂无到期词。继续学新词,或等熟练度到期。",
      onStart: (modeId) => startSession(poolArea, dueWords, modeId, activeId, router),
    }),
    poolCard({
      title: "错题本",
      desc: "答错过的词,每次答错计数 +1,连续答对 3 次自动出本。",
      count: wrongWords.length,
      emptyHint: "错题本空空如也,继续保持。",
      onStart: (modeId) => startSession(poolArea, wrongWords, modeId, activeId, router),
    }),
  ]));

  host.appendChild(poolArea);
}

function poolCard({ title, desc, count, emptyHint, onStart }) {
  const modeSelect = el("select", {},
    listModes().map((m) => el("option", { value: m.id }, m.name))
  );

  const startBtn = el("button", { class: "primary" }, "▶ 开始");
  startBtn.disabled = count === 0;
  startBtn.addEventListener("click", () => onStart(modeSelect.value));

  return el("div", { class: "card" }, [
    el("h3", { style: "margin-top:0" }, title),
    el("div", { class: "label", style: "margin-bottom:12px" }, desc),
    el("div", { class: "value", style: "font-size:36px" }, String(count)),
    count === 0
      ? el("div", { class: "label", style: "margin:12px 0" }, emptyHint)
      : el("div", { class: "row", style: "margin-top:16px; gap:8px; flex-wrap:wrap" }, [
          el("span", { class: "label" }, "玩法"),
          modeSelect,
          startBtn,
        ]),
  ]);
}

async function startSession(host, words, modeId, wordlistId, router) {
  const mode = getMode(modeId);
  if (!mode || !words.length) return;

  // 洗牌
  const shuffled = [...words].sort(() => Math.random() - 0.5);

  host.innerHTML = "";
  const container = el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "row between", style: "margin-bottom:16px" }, [
      el("strong", {}, `复习中 · ${mode.name}`),
      el("button", { class: "ghost", onClick: () => router.go("/review") }, "退出"),
    ]),
  ]);
  const modeHost = el("div", {});
  container.appendChild(modeHost);
  host.appendChild(container);

  const economy = await store.getEconomy();
  const session = new Session({
    words: shuffled,
    mode,
    wordlistId,
    economy,
    onFinish: (summary) => {
      const acc = summary.total ? Math.round(summary.accuracy * 100) : 0;
      modeHost.innerHTML = "";
      modeHost.appendChild(el("div", { style: "text-align:center; padding:20px" }, [
        el("h3", {}, "✅ 复习完成"),
        el("div", {}, `${summary.correct} / ${summary.total} 正确(${acc}%)`),
        el("div", { class: "row", style: "justify-content:center; gap:8px; margin-top:16px" }, [
          el("button", { class: "ghost", onClick: () => router.go("/") }, "回首页"),
          el("button", { class: "primary", onClick: () => router.go("/review") }, "再复习一轮"),
        ]),
      ]));
    },
  });
  session.renderCurrent(modeHost);

  container.scrollIntoView({ behavior: "smooth", block: "start" });
}
