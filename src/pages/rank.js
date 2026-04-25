/**
 * 段位赛页。
 *   landing    显示当前段位、战绩、进度条、每日挑战入口、段位阶梯
 *   ?tier=xxx  直接开打指定段位
 *   ?daily=1   每日挑战(固定用当前段位)
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadWordlist } from "../core/wordlist.js";
import {
  TIERS, TIER_PARAMS, getRankState, tierByPoints, pickWordsForMatch,
  settleMatch, dailyChallengeDoneToday,
} from "../core/rank-engine.js";
import { makeMixedMode } from "../modes/mixed.js";
import { Session } from "../core/session.js";

export async function render(ctx) {
  const { host, router, query } = ctx;

  if (query.tier) {
    await runMatch(host, router, query.tier, !!query.daily);
    return;
  }
  await renderLanding(host, router);
}

async function renderLanding(host, router) {
  const state = await getRankState();
  const cur = tierByPoints(state.points);
  const pointsInTier = state.points - cur.minPoints;
  const pct = Math.round((pointsInTier / (cur.maxPoints - cur.minPoints)) * 100);
  const dailyDone = dailyChallengeDoneToday(state);

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("h2", { style: "margin:0" }, "🏆 段位赛"),
    el("div", { class: "row", style: "gap:8px" }, [
      el("span", { class: "pill" }, `🏅 最高 ${state.highest}`),
      el("span", { class: "pill ok" }, `胜 ${state.wins}`),
      el("span", { class: "pill err" }, `负 ${state.losses}`),
    ]),
  ]));

  // 当前段位大卡
  host.appendChild(el("div", { class: "card" }, [
    el("div", { style: "text-align:center; padding:12px 0" }, [
      el("div", { style: "font-size:42px; font-weight:700" }, cur.label),
      el("div", { class: "label", style: "margin-top:4px" }, `积分 ${state.points} / ${cur.maxPoints}`),
    ]),
    el("div", { class: "progress", style: "margin-top:8px" }, [
      el("div", { class: "bar", style: `width:${pct}%; background:${cur.color}` }),
    ]),
    el("div", { class: "row", style: "margin-top:16px; justify-content:center; gap:8px; flex-wrap:wrap" }, [
      el("button", {
        class: "primary",
        onClick: () => router.go("/rank", { tier: cur.key }),
      }, `▶ 挑战 ${cur.label}`),
      el("button", {
        class: dailyDone ? "ghost" : "primary",
        disabled: dailyDone,
        onClick: () => router.go("/rank", { tier: cur.key, daily: 1 }),
      }, dailyDone ? "✓ 今日挑战已完成" : "⚡ 每日挑战(+30)"),
    ]),
    state.streak > 1
      ? el("div", { class: "feedback ok", style: "margin-top:8px" }, `🔥 连胜 ${state.streak} 场!下场 +${Math.min(state.streak, 5)} 奖励`)
      : null,
  ]));

  // 段位阶梯
  host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "section-title" }, "段位阶梯"),
    el("div", { class: "grid cols-3" }, TIERS.map((t) => tierRow(t, cur, router))),
  ]));

  // 规则
  host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "section-title" }, "规则说明"),
    el("ul", { style: "margin:8px 0; padding-left:20px; color:var(--fg-dim); line-height:1.8" }, [
      el("li", {}, "每场比赛错词 ≤ 容错数 即算胜利;超时算败"),
      el("li", {}, "胜 +20,连胜每场额外 +min(连胜,5)"),
      el("li", {}, "败 −15,但每天第一败有保护不扣分(只重置连胜)"),
      el("li", {}, "每日挑战每天一次,赢了额外 +30"),
      el("li", {}, "词池按段位切分:越高段越接近完整词表"),
    ]),
  ]));
}

function tierRow(tier, currentTier, router) {
  const unlocked = tier.index <= currentTier.index;
  const p = TIER_PARAMS[tier.big];
  return el("div", {
    class: "stat",
    style: `cursor:${unlocked ? "pointer" : "not-allowed"}; opacity:${unlocked ? 1 : 0.45}; border-left:4px solid ${tier.color}`,
    onClick: unlocked ? () => router.go("/rank", { tier: tier.key }) : null,
  }, [
    el("div", { style: "font-weight:600; font-size:15px" }, tier.label + (tier.index === currentTier.index ? " · 当前" : "")),
    el("div", { class: "label", style: "margin-top:4px" },
      `${p.wordCount}词 / ${p.timeLimit}s / 容错${p.maxWrong}`),
    el("div", { class: "label", style: "margin-top:2px; font-size:11px" },
      `积分 ${tier.minPoints}–${tier.maxPoints}`),
  ]);
}

async function runMatch(host, router, tierKey, isDaily) {
  const tier = TIERS.find((t) => t.key === tierKey);
  if (!tier) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "未知段位"),
      el("button", { class: "primary", onClick: () => router.go("/rank") }, "返回"),
    ]));
    return;
  }

  const activeId = await store.getSetting("activeWordlist", "cet6");
  let wordlist;
  try {
    wordlist = await loadWordlist(activeId);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "词表加载失败"),
      el("div", { class: "feedback err" }, e.message),
      el("button", { class: "primary", onClick: () => router.go("/rank") }, "返回"),
    ]));
    return;
  }

  const p = TIER_PARAMS[tier.big];
  const words = pickWordsForMatch(tier, wordlist);
  const mode = makeMixedMode(p.modes, `${tier.label} 混合`);

  const timerPill = el("span", { class: "pill" }, `⏱ ${p.timeLimit}s`);
  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("button", { class: "ghost", onClick: () => router.go("/rank") }, "← 退出"),
    ]),
    el("div", { style: "text-align:center" }, [
      el("div", { style: "font-weight:700; font-size:18px" }, tier.label + (isDaily ? " · 每日挑战" : "")),
      el("div", { class: "label" }, `${p.wordCount}词 / 容错 ${p.maxWrong} / ${p.modes.length} 玩法混合`),
    ]),
    el("div", { class: "row", style: "gap:8px" }, [timerPill]),
  ]));

  const modeHost = el("div", {});
  host.appendChild(modeHost);

  const economy = await store.getEconomy();
  const session = new Session({
    words,
    mode,
    wordlistId: activeId,
    economy,
    timeLimit: p.timeLimit,
    onTick: (remainMs) => {
      const s = Math.max(0, Math.ceil(remainMs / 1000));
      timerPill.textContent = `⏱ ${s}s`;
      timerPill.className = "pill" + (s <= 10 ? " err" : s <= 30 ? " warn" : "");
    },
    onFinish: async (summary) => {
      const result = await settleMatch({ tierKey: tier.key, summary, isDaily });
      renderMatchResult(modeHost, router, tier, summary, result);
    },
  });
  session.renderCurrent(modeHost);
}

function renderMatchResult(host, router, tier, summary, result) {
  host.innerHTML = "";
  const acc = Math.round(summary.accuracy * 100);
  const deltaStr = result.delta > 0 ? `+${result.delta}` : result.delta < 0 ? `${result.delta}` : "±0";
  const title = result.win ? "🎉 胜利" : summary.timedOut ? "⏱ 超时失败" : "失败";
  const newTierChanged = result.newTier.key !== tier.key;

  host.appendChild(el("div", { class: "card", style: "text-align:center" }, [
    el("h2", { style: "margin:0" }, title),
    el("div", { class: "grid cols-3", style: "margin:20px 0" }, [
      stat("正确率", `${acc}%`, `${summary.correct}/${summary.total}`),
      stat("错词数", String(result.wrong), `容错 ${result.maxWrong}`),
      stat("积分", deltaStr, `当前 ${result.newState.points}`),
    ]),
    newTierChanged
      ? el("div", { class: "feedback ok", style: "font-size:18px; padding:12px" },
          `🎊 段位变动:${tier.label} → ${result.newTier.label}`)
      : null,
    result.note ? el("div", { class: "feedback warn" }, result.note) : null,
    result.newState.streak >= 2
      ? el("div", { class: "feedback ok" }, `🔥 连胜 ${result.newState.streak} 场`)
      : null,
    el("div", { class: "row", style: "justify-content:center; gap:8px; margin-top:8px" }, [
      el("button", { class: "ghost", onClick: () => router.go("/rank") }, "回段位大厅"),
      el("button", { class: "primary", onClick: () => router.go("/rank", { tier: result.newTier.key }) }, "再战一场"),
    ]),
  ]));
}

function stat(label, value, sub) {
  return el("div", { class: "stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, value),
    sub ? el("div", { class: "sub" }, sub) : null,
  ]);
}
