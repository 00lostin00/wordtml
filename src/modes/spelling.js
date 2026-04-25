/**
 * 玩法:拼写
 * 给中文 + 首字母,键盘敲英文。
 * 规则:完全一致才算对(大小写和空格不敏感)。允许"看答案"但看了算错。
 */
import { el } from "../ui/components.js";
import { itemBar } from "./item-tools.js";

function normalize(s) {
  return (s || "").trim().toLowerCase();
}

export default {
  id: "spelling",
  name: "拼写",
  description: "看中文,键盘敲英文",

  render(ctx) {
    const { word, index, total, onAnswer } = ctx;
    const startedAt = Date.now();
    const answer = word.word;
    const firstChar = answer[0] || "";
    const hint = firstChar + "_".repeat(Math.max(0, answer.length - 1));

    const root = el("div", { class: "mode-host" });

    root.appendChild(el("div", { class: "row between" }, [
      el("span", { class: "pill" }, `第 ${index + 1} / ${total} 题`),
      el("span", { class: "pill" }, "拼写"),
    ]));
    root.appendChild(el("div", { class: "progress" }, [
      el("div", { class: "bar", style: `width:${(index / total) * 100}%` }),
    ]));
    const tools = itemBar(ctx);
    if (tools) root.appendChild(tools);

    const qCard = el("div", { class: "question-card" }, [
      word.pos ? el("span", { class: "pos" }, word.pos) : null,
      el("div", { class: "prompt", style: "font-size:26px" }, (word.defs_cn || []).join("; ")),
      el("div", { class: "phonetic", style: "letter-spacing:4px; font-family:monospace" }, hint),
    ]);
    root.appendChild(qCard);

    const input = el("input", {
      type: "text",
      placeholder: "敲入单词,回车提交",
      autocomplete: "off",
      spellcheck: "false",
      style: "font-size:20px; text-align:center; letter-spacing:2px",
    });
    const inputWrap = el("div", { class: "row", style: "justify-content:center" }, [input]);
    root.appendChild(inputWrap);

    const feedback = el("div", { class: "feedback" });
    root.appendChild(feedback);

    const actions = el("div", { class: "row", style: "justify-content:center; gap:8px" });
    const submitBtn = el("button", { class: "primary" }, "提交");
    const revealBtn = el("button", { class: "ghost" }, "看答案");
    actions.appendChild(submitBtn);
    actions.appendChild(revealBtn);
    root.appendChild(actions);

    setTimeout(() => input.focus(), 50);

    let settled = false;
    const settle = (correct, extra = {}) => {
      if (settled) return;
      settled = true;
      input.disabled = true;
      submitBtn.disabled = true;
      revealBtn.disabled = true;
      const responseMs = Date.now() - startedAt;
      feedback.textContent = correct ? `✓ ${answer}` : `✗ 正确答案:${answer}`;
      feedback.className = "feedback " + (correct ? "ok" : "err");
      setTimeout(() => {
        onAnswer({
          correct,
          quality: correct ? (responseMs < 5000 ? 5 : 4) : 1,
          responseMs,
          ...extra,
        });
      }, correct ? 600 : 1400);
    };

    const submit = () => {
      const typed = normalize(input.value);
      settle(typed === normalize(answer));
    };

    submitBtn.addEventListener("click", submit);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submit();
    });
    revealBtn.addEventListener("click", () => settle(false, { revealed: true }));

    return root;
  },
};
