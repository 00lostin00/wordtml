export const ITEM_DEFS = {
  hint: {
    kind: "hint",
    name: "提示",
    icon: "🔍",
    price: 10,
    desc: "选择题中亮出正确选项的关键词。",
  },
  skip: {
    kind: "skip",
    name: "跳过",
    icon: "⏭",
    price: 20,
    desc: "跳过当前题，不计入错题和本场总题数。",
  },
  extend: {
    kind: "extend",
    name: "延时",
    icon: "⏱",
    price: 30,
    desc: "Boss/段位赛限时场景追加 30 秒。",
  },
  xray: {
    kind: "xray",
    name: "透视",
    icon: "💡",
    price: 15,
    desc: "选择题中排除一个错误选项。",
  },
};

export const ITEM_ORDER = ["hint", "skip", "extend", "xray"];

export function freshItems() {
  return { hint: 0, skip: 0, extend: 0, xray: 0 };
}

export function normalizeEconomy(eco) {
  const next = eco || { coins: 0, items: freshItems() };
  next.coins = Number(next.coins || 0);
  next.items = { ...freshItems(), ...(next.items || {}) };
  return next;
}

export async function buyItem(store, kind, amount = 1) {
  const def = ITEM_DEFS[kind];
  if (!def) throw new Error("未知道具: " + kind);
  const qty = Math.max(1, Number(amount || 1));
  const eco = normalizeEconomy(await store.getEconomy());
  const cost = def.price * qty;
  if (eco.coins < cost) {
    return { ok: false, reason: "金币不足", economy: eco };
  }
  eco.coins -= cost;
  eco.items[kind] = (eco.items[kind] || 0) + qty;
  await store.setEconomy(eco);
  return { ok: true, economy: eco, cost, amount: qty };
}
