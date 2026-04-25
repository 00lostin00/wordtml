import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { getIndex } from "../core/wordlist.js";
import { getLocalDbStatus } from "../core/local-db.js";

export async function render(ctx) {
  const { host, router } = ctx;

  const index = await getIndex();
  const activeId = await store.getSetting("activeWordlist", "cet6");
  const dailyNew = await store.getSetting("dailyNew", 20);
  const dailyReviewCap = await store.getSetting("dailyReviewCap", 100);
  const localDb = await loadLocalDbStatus();

  const wlSelect = el("select", {}, index.wordlists.map((w) =>
    el("option", { value: w.id }, `${w.name}(${w.total} 词)`)
  ));
  wlSelect.value = activeId;

  const newInput = el("input", { type: "number", min: "0", max: "200", value: String(dailyNew) });
  const revInput = el("input", { type: "number", min: "0", max: "500", value: String(dailyReviewCap) });

  const saveBtn = el("button", { class: "primary" }, "保存");
  const savedHint = el("span", { class: "pill ok", style: "display:none" }, "已保存");

  saveBtn.addEventListener("click", async () => {
    await store.setSetting("activeWordlist", wlSelect.value);
    await store.setSetting("dailyNew", Number(newInput.value));
    await store.setSetting("dailyReviewCap", Number(revInput.value));
    savedHint.style.display = "";
    setTimeout(() => (savedHint.style.display = "none"), 1500);
  });

  host.appendChild(el("div", { class: "card" }, [
    el("h2", { style: "margin-top:0" }, "⚙️ 学习设置"),
    row("当前词表", wlSelect),
    row("每日新词目标", newInput),
    row("每日复习上限", revInput),
    el("div", { class: "row", style: "margin-top:16px; gap:12px;" }, [saveBtn, savedHint]),
  ]));

  // 数据管理
  const exportBtn = el("button", {}, "导出进度");
  const importInput = el("input", { type: "file", accept: "application/json", style: "display:none" });
  const importBtn = el("button", {}, "导入进度");
  const resetBtn = el("button", { class: "ghost" }, "清空浏览器数据");
  const dataHint = el("div", { class: "feedback", style: "margin-top:8px" });

  exportBtn.addEventListener("click", async () => {
    const dump = await store.exportAll();
    const blob = new Blob([JSON.stringify(dump, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `wordtml-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });

  importBtn.addEventListener("click", () => importInput.click());
  importInput.addEventListener("change", async () => {
    const f = importInput.files[0];
    if (!f) return;
    try {
      const dump = JSON.parse(await f.text());
      await store.importAll(dump);
      dataHint.textContent = "✓ 导入完成";
      dataHint.className = "feedback ok";
    } catch (e) {
      dataHint.textContent = "✗ 导入失败:" + e.message;
      dataHint.className = "feedback err";
    }
  });

  resetBtn.addEventListener("click", async () => {
    if (!confirm("真的要清空浏览器 IndexedDB 数据?SQLite 数据库不会被删除。")) return;
    for (const name of ["progress", "wrongbook", "settings", "stats", "sessions", "mapProgress", "economy", "rankHistory", "achievements", "examAttempts"]) {
      await store.clear(name);
    }
    dataHint.textContent = "✓ 已清空";
    dataHint.className = "feedback ok";
    setTimeout(() => router.go("/"), 800);
  });

  host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
    el("h3", { style: "margin-top:0" }, "📦 数据管理"),
    localDb.ok
      ? el("div", { class: "feedback ok", style: "text-align:left; margin-bottom:12px" },
          `SQLite 已启用: ${localDb.dbPath} · 做题记录 ${localDb.examAttempts} 条 · 抽题历史 ${localDb.practiceHistory} 条`)
      : el("div", { class: "feedback warn", style: "text-align:left; margin-bottom:12px" },
          `SQLite 暂不可用: ${localDb.error}`),
    el("div", { class: "label", style: "margin-bottom:12px" },
      "导出/导入按钮管理浏览器 IndexedDB。SQLite 数据库保存在项目根目录,清浏览器数据不会删除它。"),
    el("div", { class: "row", style: "gap:8px; flex-wrap:wrap" }, [exportBtn, importBtn, resetBtn, importInput]),
    dataHint,
  ]));
}

async function loadLocalDbStatus() {
  try {
    return await getLocalDbStatus();
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

function row(label, ctrl) {
  return el("div", { class: "row", style: "margin-top:12px; gap:12px;" }, [
    el("div", { style: "min-width:140px; color:var(--fg-dim)" }, label),
    ctrl,
  ]);
}
