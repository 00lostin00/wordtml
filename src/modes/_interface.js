/**
 * 玩法统一接口。所有玩法模块必须默认导出以下结构:
 *
 *   export default {
 *     id: "choice-en",
 *     name: "英译中选择",
 *     description: "给单词选中文释义",
 *     render(ctx) -> HTMLElement
 *   }
 *
 * ctx 结构(由 Session 注入):
 *   word      当前词
 *   pool      本次会话的全部词(用于抽干扰项)
 *   index     当前题序号
 *   total     本次题目总数
 *   items     当前道具库存快照:{ hint, skip, extend, xray }
 *   hasTimer  当前 Session 是否限时
 *   useItem(kind)      使用道具,返回 { ok, message, economy }
 *   onAnswer(result)   回传结果:{ correct: boolean, quality?: 0..5, responseMs?: number }
 */

import choiceEn from "./choice-en.js";
import choiceCn from "./choice-cn.js";
import flashcard from "./flashcard.js";
import spelling from "./spelling.js";
import dictation from "./dictation.js";

export const MODES = {
  [choiceEn.id]: choiceEn,
  [choiceCn.id]: choiceCn,
  [flashcard.id]: flashcard,
  [spelling.id]: spelling,
  [dictation.id]: dictation,
  // 例句填空 (cloze) 需要词表里有 examples 才能开,当前 cet6 词表无例句,留到 Phase 5。
};

export function getMode(id) {
  return MODES[id] || null;
}

export function listModes() {
  return Object.values(MODES);
}
