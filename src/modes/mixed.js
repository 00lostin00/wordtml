/**
 * 混合玩法工厂。
 * 给一组 modeId,返回一个合成 Mode,每道题随机选一个 submode 渲染。
 *
 * 用于精英关(2 种混合)、Boss 关(4 种混合)。
 */
import { getMode } from "./_interface.js";

export function makeMixedMode(modeIds, label = "混合") {
  const valid = modeIds.map(getMode).filter(Boolean);
  if (!valid.length) throw new Error("mixed mode 需要至少一个有效 subMode");

  return {
    id: "mixed:" + modeIds.join("+"),
    name: label,
    description: `随机 ${valid.map((m) => m.name).join(" / ")}`,
    render(ctx) {
      const sub = valid[Math.floor(Math.random() * valid.length)];
      return sub.render(ctx);
    },
  };
}
