import { ITEM_DEFS, ITEM_ORDER, buyItem, normalizeEconomy } from "../core/items.js";
import { store } from "../core/store.js";
import { el } from "../ui/components.js";

export async function render(ctx) {
  const { host, router } = ctx;
  let economy = normalizeEconomy(await store.getEconomy());

  const coins = el("span", { class: "pill ok" }, `金币 ${economy.coins}`);
  const hint = el("div", { class: "feedback", style: "margin-top:12px" }, "");
  const grid = el("div", { class: "grid cols-2", style: "margin-top:16px" });

  const refresh = (next) => {
    economy = normalizeEconomy(next);
    coins.textContent = `金币 ${economy.coins}`;
    grid.innerHTML = "";
    for (const kind of ITEM_ORDER) {
      grid.appendChild(itemCard(kind, economy, async (amount) => {
        const result = await buyItem(store, kind, amount);
        refresh(result.economy);
        hint.textContent = result.ok
          ? `已购买 ${ITEM_DEFS[kind].name} x${amount}，花费 ${result.cost} 金币`
          : result.reason;
        hint.className = "feedback " + (result.ok ? "ok" : "err");
      }));
    }
  };

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("h2", { style: "margin:0" }, "道具商店"),
      el("div", { class: "label", style: "margin-top:4px" }, "金币来自地图升星奖励，后续挑战也可以继续接入奖励。"),
    ]),
    el("div", { class: "row", style: "gap:8px" }, [
      coins,
      el("button", { class: "ghost", onClick: () => router.go("/") }, "回首页"),
    ]),
  ]));

  host.appendChild(el("div", { class: "card" }, [
    el("div", { class: "section-title" }, "库存与购买"),
    grid,
    hint,
  ]));

  host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "section-title" }, "使用规则"),
    el("ul", { class: "rule-list" }, [
      el("li", {}, "提示和透视只在选择题中出现。"),
      el("li", {}, "跳过会跳过当前题，不写错题、不更新熟练度，也不计入本场总题数。"),
      el("li", {}, "延时只在 Boss、段位赛等限时场景可用，每次增加 30 秒。"),
    ]),
  ]));

  refresh(economy);
}

function itemCard(kind, economy, onBuy) {
  const def = ITEM_DEFS[kind];
  const count = Number((economy.items && economy.items[kind]) || 0);
  const canBuyOne = economy.coins >= def.price;
  const canBuyFive = economy.coins >= def.price * 5;

  return el("div", { class: "shop-card" }, [
    el("div", { class: "shop-icon" }, def.icon),
    el("div", { class: "shop-main" }, [
      el("div", { class: "row between" }, [
        el("h3", { style: "margin:0" }, def.name),
        el("span", { class: "pill" }, `库存 ${count}`),
      ]),
      el("div", { class: "label", style: "margin-top:6px" }, def.desc),
      el("div", { class: "row", style: "margin-top:14px; gap:8px" }, [
        el("span", { class: "pill" }, `${def.price} 金币/个`),
        el("button", { class: "primary", disabled: !canBuyOne, onClick: () => onBuy(1) }, "买 1 个"),
        el("button", { disabled: !canBuyFive, onClick: () => onBuy(5) }, "买 5 个"),
      ]),
    ]),
  ]);
}
