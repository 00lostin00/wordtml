/**
 * 地图页。
 *   无 query       → 章节列表
 *   ?chapter=xxx   → 进入某章节的地图
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import {
  getMapIndex, loadChapter,
  getChapterProgress, nodeState, chapterCompletion,
} from "../core/map-engine.js";

export async function render(ctx) {
  const { host, router, query } = ctx;
  const eco = await store.getEconomy();

  if (!query.chapter) {
    await renderChapterList(host, router, eco);
  } else {
    await renderChapterMap(host, router, query.chapter, eco);
  }
}

async function renderChapterList(host, router, eco) {
  const idx = await getMapIndex();

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("h2", { style: "margin:0" }, "🗺️ 地图闯关"),
    el("div", { class: "row", style: "gap:12px" }, [
      el("span", { class: "pill" }, `💰 ${eco.coins}`),
    ]),
  ]));

  if (!idx.chapters.length) {
    host.appendChild(el("div", { class: "empty" }, "还没有可玩的章节。"));
    return;
  }

  const grid = el("div", { class: "grid cols-2" });
  for (const meta of idx.chapters) {
    const card = await renderChapterCard(meta, router);
    grid.appendChild(card);
  }
  host.appendChild(grid);
}

async function renderChapterCard(meta, router) {
  let chapter = null;
  let comp = null;
  let err = null;
  try {
    chapter = await loadChapter(meta.id);
    const progress = await getChapterProgress(meta.id);
    comp = chapterCompletion(chapter, progress);
  } catch (e) {
    err = e;
  }

  if (err) {
    return el("div", { class: "card" }, [
      el("div", { style: "font-size:24px" }, `${meta.icon || "🗺️"} ${meta.name}`),
      el("div", { class: "feedback err" }, err.message),
    ]);
  }

  const pct = Math.round(comp.percent * 100);
  const card = el("div", {
    class: "card",
    style: "cursor:pointer; transition:transform 0.12s",
    onClick: () => router.go("/map", { chapter: meta.id }),
  }, [
    el("div", { class: "row between" }, [
      el("div", { style: "font-size:28px" }, `${chapter.icon || meta.icon || "🗺️"} ${chapter.name}`),
      el("span", { class: "pill" }, chapter.subtitle || ""),
    ]),
    el("div", { class: "label", style: "margin-top:8px" },
      `通关 ${comp.cleared}/${comp.total} · 星数 ${comp.stars}/${comp.maxStars}`),
    el("div", { class: "progress", style: "margin-top:12px" }, [
      el("div", { class: "bar", style: `width:${pct}%` }),
    ]),
  ]);
  card.addEventListener("mouseenter", () => card.style.transform = "translateY(-2px)");
  card.addEventListener("mouseleave", () => card.style.transform = "");
  return card;
}

async function renderChapterMap(host, router, chapterId, eco) {
  let chapter;
  try {
    chapter = await loadChapter(chapterId);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "章节加载失败"),
      el("div", { class: "feedback err" }, e.message),
      el("button", { class: "primary", onClick: () => router.go("/map") }, "返回章节列表"),
    ]));
    return;
  }
  const progress = await getChapterProgress(chapterId);
  const comp = chapterCompletion(chapter, progress);

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("button", { class: "ghost", onClick: () => router.go("/map") }, "← 返回章节"),
    ]),
    el("div", { style: "text-align:center" }, [
      el("div", { style: "font-size:22px; font-weight:600" }, `${chapter.icon} ${chapter.name}`),
      el("div", { class: "label" }, chapter.subtitle || ""),
    ]),
    el("div", { class: "row", style: "gap:8px" }, [
      el("span", { class: "pill" }, `⭐ ${comp.stars}/${comp.maxStars}`),
      el("span", { class: "pill" }, `💰 ${eco.coins}`),
    ]),
  ]));

  // 地图容器
  const theme = chapter.theme || {};
  const canvas = el("div", {
    class: "card",
    style: [
      "position:relative",
      "height:720px",
      "overflow:hidden",
      theme.bg ? `background:linear-gradient(180deg, ${theme.bg} 0%, var(--bg-card) 100%)` : "",
    ].filter(Boolean).join(";"),
  });

  // SVG 连线层
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("preserveAspectRatio", "none");
  Object.assign(svg.style, {
    position: "absolute",
    inset: "0",
    width: "100%",
    height: "100%",
    pointerEvents: "none",
  });

  const stateById = new Map();
  for (const node of chapter.nodes) {
    stateById.set(node.id, nodeState(node, progress));
  }

  for (const node of chapter.nodes) {
    const st = stateById.get(node.id);
    if (!st.visible) continue;
    for (const reqId of node.requires || []) {
      const from = chapter.nodes.find((n) => n.id === reqId);
      if (!from) continue;
      const fromSt = stateById.get(reqId);
      if (!fromSt || !fromSt.visible) continue;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", from.x);
      line.setAttribute("y1", 100 - from.y);
      line.setAttribute("x2", node.x);
      line.setAttribute("y2", 100 - node.y);
      line.setAttribute("stroke", theme.path || "#3a4050");
      line.setAttribute("stroke-width", "0.6");
      line.setAttribute("stroke-dasharray", st.state === "locked" ? "1.5,1.5" : "");
      line.setAttribute("stroke-linecap", "round");
      svg.appendChild(line);
    }
  }
  canvas.appendChild(svg);

  // 节点层
  for (const node of chapter.nodes) {
    const st = stateById.get(node.id);
    if (!st.visible) continue;
    canvas.appendChild(renderNode(node, st, chapter, router));
  }

  host.appendChild(canvas);
}

const NODE_STYLES = {
  normal:   { emoji: "🌿", ringColor: "#6aa7ff" },
  elite:    { emoji: "⚔️", ringColor: "#c77dff" },
  boss:     { emoji: "👹", ringColor: "#ff6a6a" },
  treasure: { emoji: "💎", ringColor: "#f2b94a" },
  hidden:   { emoji: "❓", ringColor: "#aaa" },
};

function renderNode(node, st, chapter, router) {
  const style = NODE_STYLES[node.type] || NODE_STYLES.normal;
  const sizePx = node.type === "boss" ? 76 : node.type === "elite" ? 64 : 56;

  const btn = el("button", {
    class: "map-node",
    title: node.name,
    style: [
      "position:absolute",
      `left:calc(${node.x}% - ${sizePx / 2}px)`,
      `top:calc(${100 - node.y}% - ${sizePx / 2}px)`,
      `width:${sizePx}px`,
      `height:${sizePx}px`,
      "border-radius:50%",
      "padding:0",
      "border:3px solid " + style.ringColor,
      "background:var(--bg-card)",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "font-size:" + (node.type === "boss" ? "32px" : "24px"),
      "cursor:" + (st.state === "locked" ? "not-allowed" : "pointer"),
      "opacity:" + (st.state === "locked" ? "0.4" : "1"),
      "box-shadow:0 4px 12px rgba(0,0,0,0.4)",
      "transition:transform 0.12s",
    ].join(";"),
  }, style.emoji);

  btn.addEventListener("mouseenter", () => {
    if (st.state !== "locked") btn.style.transform = "translate(0,-3px) scale(1.08)";
  });
  btn.addEventListener("mouseleave", () => btn.style.transform = "");

  btn.addEventListener("click", () => {
    if (st.state === "locked") return;
    router.go("/stage", { chapter: chapter.id, node: node.id });
  });

  // 星级徽章
  if (st.stars > 0) {
    const stars = "⭐".repeat(st.stars);
    const badge = el("div", {
      style: [
        "position:absolute",
        `left:calc(${node.x}% - 32px)`,
        `top:calc(${100 - node.y}% + ${sizePx / 2 - 6}px)`,
        "width:64px",
        "text-align:center",
        "font-size:14px",
        "pointer-events:none",
      ].join(";"),
    }, stars);
    const wrap = el("div", { style: "display:contents" }, [btn, badge]);
    // 小名字标签
    const name = el("div", {
      style: [
        "position:absolute",
        `left:calc(${node.x}% - 60px)`,
        `top:calc(${100 - node.y}% - ${sizePx / 2 + 24}px)`,
        "width:120px",
        "text-align:center",
        "font-size:12px",
        "color:var(--fg-dim)",
        "pointer-events:none",
        "text-shadow:0 1px 2px rgba(0,0,0,0.6)",
      ].join(";"),
    }, node.name);
    wrap.appendChild(name);
    return wrap;
  }

  const nameLabel = el("div", {
    style: [
      "position:absolute",
      `left:calc(${node.x}% - 60px)`,
      `top:calc(${100 - node.y}% - ${sizePx / 2 + 24}px)`,
      "width:120px",
      "text-align:center",
      "font-size:12px",
      "color:" + (st.state === "locked" ? "var(--fg-faint)" : "var(--fg-dim)"),
      "pointer-events:none",
      "text-shadow:0 1px 2px rgba(0,0,0,0.6)",
    ].join(";"),
  }, node.name);

  const wrap = el("div", { style: "display:contents" }, [btn, nameLabel]);
  return wrap;
}
