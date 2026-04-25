import { ITEM_DEFS } from "../core/items.js";
import { el } from "../ui/components.js";

function countOf(ctx, kind) {
  return Number((ctx.items && ctx.items[kind]) || 0);
}

export function itemBar(ctx, handlers = {}) {
  if (!ctx.useItem) return null;

  const feedback = el("span", { class: "item-feedback" }, "");
  const buttons = new Map();

  const refresh = (economy) => {
    if (economy && economy.items) ctx.items = economy.items;
    for (const [kind, btn] of buttons.entries()) {
      const count = countOf(ctx, kind);
      const needsTimer = kind === "extend" && !ctx.hasTimer;
      btn.querySelector("[data-count]").textContent = String(count);
      btn.disabled = count <= 0 || needsTimer;
    }
  };

  const makeButton = (kind, label, action) => {
    const def = ITEM_DEFS[kind];
    const btn = el("button", { class: "tool-btn", title: def.desc }, [
      el("span", {}, `${def.icon} ${label}`),
      el("span", { class: "tool-count", "data-count": "1" }, String(countOf(ctx, kind))),
    ]);
    btn.addEventListener("click", async () => {
      if (btn.disabled) return;
      const result = await ctx.useItem(kind);
      refresh(result.economy);
      feedback.textContent = result.message || "";
      feedback.className = "item-feedback " + (result.ok ? "ok" : "err");
      if (!result.ok) return;
      if (action) action(result);
    });
    buttons.set(kind, btn);
    return btn;
  };

  const nodes = [];
  if (handlers.hint) nodes.push(makeButton("hint", "提示", handlers.hint));
  nodes.push(makeButton("skip", "跳过", handlers.skip));
  nodes.push(makeButton("extend", "+30秒", handlers.extend));
  if (handlers.xray) nodes.push(makeButton("xray", "透视", handlers.xray));

  const bar = el("div", { class: "item-bar" }, [
    el("div", { class: "item-bar-title" }, "道具"),
    ...nodes,
    feedback,
  ]);
  refresh();
  return bar;
}
