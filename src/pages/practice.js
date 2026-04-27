/**
 * 随机刷题入口 /practice
 */
import { el } from "../ui/components.js";
import {
  PRACTICE_TYPES,
  getPracticeUnits,
  pickRandomUnit,
  unitQuery,
  unitSourceLabel,
  unitTypeCounts,
} from "../core/exam-practice.js";
import { tryGetPracticeHistory, trySavePracticeHistory } from "../core/local-db.js";

const RECENT_KEY = "wordtml.practice.recent";

export async function render(ctx) {
  const { host, router } = ctx;

  let units;
  try {
    units = await getPracticeUnits();
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "刷题池加载失败"),
      el("div", { class: "feedback err" }, e.message),
    ]));
    return;
  }

  const counts = unitTypeCounts(units);
  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("h2", { style: "margin:0" }, "随机刷题"),
      el("div", { class: "label" }, `已从可判分真题中整理出 ${units.length} 个可抽客观题/主观题子单元`),
    ]),
    el("button", { class: "ghost", onClick: () => router.go("/exams") }, "真题中心"),
  ]));

  host.appendChild(el("div", { class: "grid cols-3" },
    Object.entries(PRACTICE_TYPES).map(([type, info]) =>
      typeCard(type, info, counts[type] || 0, () => draw(router, units, type))
    )
  ));

  const recent = mergeRecent(await tryGetPracticeHistory(8), readRecent());
  host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "section-title" }, "最近抽过"),
    recent.length
      ? el("div", { class: "exam-attempt-list" }, recent.map((item) => recentRow(router, item)))
      : el("div", { class: "empty", style: "padding:18px 0" }, "还没有抽题记录。"),
  ]));
}

function typeCard(type, info, count, onDraw) {
  const disabled = count <= 0;
  return el("div", { class: "exam-type-card", style: disabled ? "opacity:0.55" : "" }, [
    el("div", { class: "row between" }, [
      el("div", { class: "exam-type-title" }, info.title),
      el("span", { class: "pill" }, `${count} 组`),
    ]),
    el("div", { class: "label", style: "margin:10px 0 16px" }, info.desc),
    el("button", {
      class: "primary",
      disabled,
      style: "width:100%",
      onClick: onDraw,
    }, "随机抽一个"),
  ]);
}

function draw(router, units, type) {
  const unit = pickRandomUnit(units, type);
  if (!unit) return;
  remember(unit);
  router.go("/random", unitQuery(unit));
}

function recentRow(router, item) {
  return el("div", { class: "row between exam-attempt-row" }, [
    el("div", {}, [
      el("div", { style: "font-weight:700" }, item.title),
      el("div", { class: "label" }, `${PRACTICE_TYPES[item.type]?.title || item.type} · ${item.source}`),
    ]),
    el("button", {
      class: "ghost",
      onClick: () => router.go("/random", { type: item.type, from: item.examId, pIdx: item.pIdx, section: item.sectionId }),
    }, "继续做"),
  ]);
}

function remember(unit) {
  const item = {
    id: unit.id,
    type: unit.type,
    examId: unit.examId,
    pIdx: unit.pIdx,
    sectionId: unit.sectionId,
    title: unit.title,
    source: unitSourceLabel(unit),
    at: Date.now(),
  };
  const recent = [item, ...readRecent().filter((old) => old.id !== item.id)].slice(0, 8);
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
  trySavePracticeHistory(item);
}

function readRecent() {
  try {
    const rows = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    return Array.isArray(rows) ? rows : [];
  } catch {
    return [];
  }
}

function mergeRecent(localRows, browserRows) {
  const map = new Map();
  for (const item of [...(localRows || []), ...(browserRows || [])]) {
    const key = item.localDbId ? `local:${item.localDbId}` : `${item.id}:${item.at}`;
    map.set(key, item);
  }
  return [...map.values()]
    .sort((a, b) => Number(b.at || 0) - Number(a.at || 0))
    .slice(0, 8);
}
