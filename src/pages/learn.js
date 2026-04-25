import { achievementNotice, el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadWordlist } from "../core/wordlist.js";
import { pickTodayBatch } from "../core/srs.js";
import { getMode, listModes } from "../modes/_interface.js";
import { Session } from "../core/session.js";

export async function render(ctx) {
  const { host, router, query } = ctx;

  const modeId = query.mode || "choice-en";
  const mode = getMode(modeId);
  if (!mode) {
    host.appendChild(pickModeView(router));
    return;
  }

  const activeId = await store.getSetting("activeWordlist", "cet6");
  const dailyNew = Number(await store.getSetting("dailyNew", 20));
  const dailyReviewCap = Number(await store.getSetting("dailyReviewCap", 100));

  let wordlist;
  try {
    wordlist = await loadWordlist(activeId);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "词表加载失败"),
      el("div", { class: "feedback err" }, String(e.message || e)),
      el("button", { class: "primary", onClick: () => router.go("/settings") }, "去设置选词表"),
    ]));
    return;
  }

  const allProgress = await store.all("progress");
  const progressMap = new Map(
    allProgress.filter((p) => p.wordlistId === activeId).map((p) => [p.wordId, p])
  );
  const batch = pickTodayBatch(wordlist.words, progressMap, {
    newCount: dailyNew,
    reviewCap: dailyReviewCap,
  });

  if (batch.length === 0) {
    host.appendChild(el("div", { class: "empty" }, [
      el("h3", {}, "🎉 今天没有待背的词"),
      el("p", {}, "已完成今日计划。可以换个词表,或等到期复习。"),
      el("button", { class: "primary", onClick: () => router.go("/") }, "回首页"),
    ]));
    return;
  }

  const container = el("div", {}, [
    el("div", { class: "row between", style: "margin-bottom:16px" }, [
      el("div", {}, [
        el("strong", {}, mode.name),
        el("span", { class: "pill", style: "margin-left:8px" }, wordlist.meta.name),
      ]),
      el("button", { class: "ghost", onClick: () => router.go("/") }, "退出"),
    ]),
  ]);
  const modeHost = el("div", {});
  container.appendChild(modeHost);
  host.appendChild(container);

  const economy = await store.getEconomy();
  const session = new Session({
    words: batch,
    mode,
    wordlistId: activeId,
    economy,
    onFinish: (summary) => showSummary(modeHost, summary, router),
  });
  session.renderCurrent(modeHost);
}

function pickModeView(router) {
  return el("div", { class: "card" }, [
    el("h3", { style: "margin-top:0" }, "选一个玩法开练"),
    el("div", { class: "grid cols-2", style: "margin-top:12px" }, listModes().map((m) =>
      el("button", {
        class: "option",
        onClick: () => router.go("/learn", { mode: m.id }),
      }, [
        el("div", { style: "font-weight:600" }, m.name),
        el("div", { class: "label", style: "margin-top:4px" }, m.description || ""),
      ])
    )),
  ]);
}

function showSummary(host, summary, router) {
  host.innerHTML = "";
  const acc = summary.total ? Math.round(summary.accuracy * 100) : 0;
  host.appendChild(el("div", { class: "card" }, [
    el("h2", { style: "margin-top:0" }, "✅ 本轮完成"),
    el("div", { class: "grid cols-3", style: "margin-top:12px" }, [
      el("div", { class: "stat" }, [
        el("div", { class: "label" }, "题数"),
        el("div", { class: "value" }, String(summary.total)),
      ]),
      el("div", { class: "stat" }, [
        el("div", { class: "label" }, "答对"),
        el("div", { class: "value" }, `${summary.correct}(${acc}%)`),
      ]),
      el("div", { class: "stat" }, [
        el("div", { class: "label" }, "用时"),
        el("div", { class: "value" }, formatDuration(summary.durationMs)),
      ]),
    ]),
    el("div", { class: "row", style: "margin-top:16px; justify-content:flex-end; gap:8px;" }, [
      el("button", { class: "ghost", onClick: () => router.go("/") }, "回首页"),
      el("button", { class: "primary", onClick: () => location.reload() }, "再来一轮"),
    ]),
    achievementNotice(summary.unlockedAchievements),
  ]));
}

function formatDuration(ms) {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} 秒`;
  return `${Math.floor(s / 60)}分${s % 60}秒`;
}
