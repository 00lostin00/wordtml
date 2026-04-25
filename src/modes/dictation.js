/**
 * 玩法:听写
 * 浏览器 SpeechSynthesis 发音 → 键盘敲单词。
 * 没有 TTS 时优雅降级为"显示音标 + 拼写"。
 */
import { el } from "../ui/components.js";
import { itemBar } from "./item-tools.js";

function normalize(s) {
  return (s || "").trim().toLowerCase();
}

function speak(text) {
  if (!("speechSynthesis" in window)) return false;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = 0.9;
    window.speechSynthesis.speak(u);
    return true;
  } catch (e) {
    return false;
  }
}

export default {
  id: "dictation",
  name: "听写",
  description: "听发音,键盘敲单词",

  render(ctx) {
    const { word, index, total, onAnswer } = ctx;
    const startedAt = Date.now();
    const answer = word.word;
    const hasTTS = "speechSynthesis" in window;

    const root = el("div", { class: "mode-host" });

    root.appendChild(el("div", { class: "row between" }, [
      el("span", { class: "pill" }, `第 ${index + 1} / ${total} 题`),
      el("span", { class: "pill" }, "听写"),
    ]));
    root.appendChild(el("div", { class: "progress" }, [
      el("div", { class: "bar", style: `width:${(index / total) * 100}%` }),
    ]));
    const tools = itemBar(ctx);
    if (tools) root.appendChild(tools);

    const playBtn = el("button", {
      class: "primary",
      style: "font-size:28px; padding:24px 36px; border-radius:999px",
    }, "🔊 播放");
    const qCard = el("div", { class: "question-card" }, [
      hasTTS ? el("div", { style: "margin-bottom:16px" }, playBtn) : el("div", { class: "phonetic" }, word.phonetic || "(无音标,TTS 也不可用)"),
      word.pos ? el("span", { class: "pos" }, word.pos) : null,
      el("div", { class: "label" }, "敲入你听到的单词"),
    ]);
    root.appendChild(qCard);

    // 自动播放一次
    if (hasTTS) setTimeout(() => speak(answer), 200);
    playBtn.addEventListener("click", () => speak(answer));

    const input = el("input", {
      type: "text",
      placeholder: "回车提交",
      autocomplete: "off",
      spellcheck: "false",
      style: "font-size:20px; text-align:center; letter-spacing:2px",
    });
    root.appendChild(el("div", { class: "row", style: "justify-content:center" }, [input]));

    const feedback = el("div", { class: "feedback" });
    root.appendChild(feedback);

    const submitBtn = el("button", { class: "primary" }, "提交");
    root.appendChild(el("div", { class: "row", style: "justify-content:center" }, [submitBtn]));

    setTimeout(() => input.focus(), 50);

    let settled = false;
    const submit = () => {
      if (settled) return;
      settled = true;
      const typed = normalize(input.value);
      const correct = typed === normalize(answer);
      input.disabled = true;
      submitBtn.disabled = true;
      const responseMs = Date.now() - startedAt;
      feedback.textContent = correct ? `✓ ${answer}` : `✗ 正确答案:${answer}`;
      feedback.className = "feedback " + (correct ? "ok" : "err");
      setTimeout(() => {
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
        onAnswer({
          correct,
          quality: correct ? (responseMs < 5000 ? 5 : 4) : 1,
          responseMs,
        });
      }, correct ? 600 : 1400);
    };

    submitBtn.addEventListener("click", submit);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submit();
    });

    return root;
  },
};
