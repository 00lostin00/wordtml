import { el, statBlock } from "../ui/components.js";
import { store } from "../core/store.js";
import { getIndex, loadWordlist } from "../core/wordlist.js";
import { pickTodayBatch } from "../core/srs.js";

export async function render(ctx) {
  const { host, router } = ctx;

  const today = new Date().toISOString().slice(0, 10);
  const stats = (await store.get("stats", today)) || { learned: 0, reviewed: 0, correct: 0, total: 0 };
  const allProgress = await store.all("progress");
  const wrongbook = await store.all("wrongbook");

  const activeId = await store.getSetting("activeWordlist", "cet6");
  const dailyNew = await store.getSetting("dailyNew", 20);
  const dailyReviewCap = await store.getSetting("dailyReviewCap", 100);

  let wordlist = null;
  let todayBatch = [];
  let wordlistErr = null;
  try {
    wordlist = await loadWordlist(activeId);
    const progressMap = new Map(allProgress.filter((p) => p.wordlistId === activeId).map((p) => [p.wordId, p]));
    todayBatch = pickTodayBatch(wordlist.words, progressMap, {
      newCount: Number(dailyNew),
      reviewCap: Number(dailyReviewCap),
    });
  } catch (e) {
    wordlistErr = e;
  }

  const index = await getIndex();
  const activeMeta = index.wordlists.find((w) => w.id === activeId);

  host.appendChild(el("div", { class: "card" }, [
    el("h2", { style: "margin-top:0" }, "今天背点什么"),
    el("div", { class: "row" }, [
      el("span", { class: "pill" }, `词表:${activeMeta ? activeMeta.name : activeId}`),
      el("span", { class: "pill" }, `新词目标 ${dailyNew}`),
      el("span", { class: "pill" }, `复习上限 ${dailyReviewCap}`),
    ]),
    wordlistErr
      ? el("div", { class: "feedback err", style: "margin-top:12px" }, `词表加载失败:${wordlistErr.message}`)
      : el("div", { class: "row", style: "margin-top:16px; gap:8px;" }, [
          el("button", { class: "primary", onClick: () => router.go("/learn", { mode: "choice-en" }) }, `▶ 开始学习(${todayBatch.length} 词)`),
          el("button", { onClick: () => router.go("/review") }, "复习错题"),
          el("button", { class: "ghost", onClick: () => router.go("/settings") }, "换词表"),
        ]),
  ]));

  host.appendChild(el("div", { class: "grid cols-4", style: "margin-top:16px" }, [
    statBlock("今日新学", stats.learned, "个"),
    statBlock("今日复习", stats.reviewed, "次"),
    statBlock("正确率", stats.total ? `${Math.round((stats.correct / stats.total) * 100)}%` : "—", stats.total ? `${stats.correct}/${stats.total}` : "尚无记录"),
    statBlock("错题本", wrongbook.length, "个待消化"),
  ]));

  host.appendChild(el("div", { class: "grid cols-3", style: "margin-top:16px" }, [
    statBlock("已学词数", allProgress.length, `共 ${wordlist ? wordlist.words.length : "?"} 词`),
    statBlock(
      "熟练度分布",
      distributionLine(allProgress),
      "陌生 → 永久",
    ),
    statBlock("到期待复习", todayBatch.length, "含新词 + 复习"),
  ]));

  host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "section-title" }, "基础玩法 · Phase 2 已开 5 种"),
    el("div", { class: "grid cols-3" }, [
      modeCard("英译中选择", "看单词选释义", true, () => router.go("/learn", { mode: "choice-en" })),
      modeCard("中译英选择", "看释义选单词", true, () => router.go("/learn", { mode: "choice-cn" })),
      modeCard("闪卡", "翻面自评熟练度", true, () => router.go("/learn", { mode: "flashcard" })),
      modeCard("拼写", "看释义敲单词", true, () => router.go("/learn", { mode: "spelling" })),
      modeCard("听写", "听发音敲单词", true, () => router.go("/learn", { mode: "dictation" })),
      modeCard("单词拼图", "乱序字母拼回单词", true, () => router.go("/learn", { mode: "puzzle" })),
    ]),
  ]));

  host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "section-title" }, "挑战入口 · Phase 3–4 已开"),
    el("div", { class: "grid cols-3" }, [
      modeCard("🗺️ 地图闯关", "主题世界 · 关卡 + 星级", true, () => router.go("/map")),
      modeCard("🏆 段位赛", "青铜→王者 · 限时混合", true, () => router.go("/rank")),
      modeCard("🛒 道具商店", "用金币购买提示/跳过/延时/透视", true, () => router.go("/shop")),
      modeCard("⚡ 快速反应", "30/60/90 秒限时连答", true, () => router.go("/rapid")),
      modeCard("🧩 单词拼图", "点击字母完成拼写", true, () => router.go("/learn", { mode: "puzzle" })),
    ]),
  ]));
}

function distributionLine(progress) {
  const buckets = [0, 0, 0, 0, 0];
  for (const p of progress) buckets[p.box] = (buckets[p.box] || 0) + 1;
  return buckets.join(" / ");
}

function modeCard(title, desc, enabled, onClick) {
  const node = el("div", {
    class: "stat",
    style: "cursor:" + (enabled ? "pointer" : "default") + ";opacity:" + (enabled ? 1 : 0.5),
    onClick: enabled ? onClick : null,
  }, [
    el("div", { class: "label" }, desc),
    el("div", { class: "value", style: "font-size:18px" }, title),
  ]);
  return node;
}
