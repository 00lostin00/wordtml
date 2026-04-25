/**
 * 真题随机刷题:把完整/近完整卷拆成可抽取的完整子单元。
 */
import { getExamIndex, loadExam } from "./exam-loader.js";

export const PRACTICE_TYPES = {
  "reading-mcq": {
    title: "仔细阅读",
    desc: "随机抽一篇阅读,带完整 5 道选择题。",
  },
  "banked-cloze": {
    title: "选词填空",
    desc: "随机抽一整段选词填空,带词库和 10 个空。",
  },
  "matching": {
    title: "段落匹配",
    desc: "随机抽一整篇段落匹配,带原文和全部题目。",
  },
  "translation": {
    title: "翻译",
    desc: "随机抽一段完整翻译题。",
  },
  "writing": {
    title: "写作",
    desc: "随机抽一道完整写作题。",
  },
};

let unitCache = null;

export async function getPracticeUnits() {
  if (unitCache) return unitCache;
  const idx = await getExamIndex();
  const playable = (idx.exams || []).filter((exam) =>
    exam.type === "cet6" && ["complete", "near-complete"].includes(exam.label)
  );
  const units = [];
  for (const entry of playable) {
    const exam = await loadExam(entry.id);
    units.push(...buildUnits(entry, exam));
  }
  unitCache = units;
  return units;
}

export async function findPracticeUnit({ type, from, pIdx }) {
  const units = await getPracticeUnits();
  return units.find((unit) =>
    unit.type === type &&
    unit.examId === from &&
    String(unit.pIdx) === String(pIdx || 0)
  ) || null;
}

export function unitTypeCounts(units) {
  const out = {};
  for (const type of Object.keys(PRACTICE_TYPES)) out[type] = 0;
  for (const unit of units) out[unit.type] = (out[unit.type] || 0) + 1;
  return out;
}

export function pickRandomUnit(units, type) {
  const pool = units.filter((unit) => unit.type === type);
  if (!pool.length) return null;
  return pool[Math.floor(Math.random() * pool.length)];
}

export function unitQuery(unit) {
  return { type: unit.type, from: unit.examId, pIdx: unit.pIdx };
}

export function unitSourceLabel(unit) {
  const month = unit.exam.month ? `${unit.exam.month}月` : "";
  const set = unit.exam.set ? `第${unit.exam.set}套` : "";
  return `${unit.exam.year || ""}年${month}${set}` || unit.exam.title || unit.examId;
}

function buildUnits(entry, exam) {
  const units = [];
  for (const section of exam.sections || []) {
    if (!sectionReady(entry, section)) continue;
    if (section.type === "reading-mcq") {
      (section.passages || []).forEach((passage, idx) => {
        if (!passage || !(passage.questions || []).length) return;
        units.push(makeUnit(entry, exam, section.type, idx, section, {
          ...section,
          title: `${section.title || "仔细阅读"} · ${passage.label || `Passage ${idx + 1}`}`,
          passages: [passage],
        }, passage.label || `Passage ${idx + 1}`));
      });
      continue;
    }
    if (!PRACTICE_TYPES[section.type]) continue;
    if (!hasContent(section)) continue;
    units.push(makeUnit(entry, exam, section.type, 0, section, section, section.title));
  }
  return units;
}

function sectionReady(entry, section) {
  const status = entry.sectionStatus || {};
  const key = section.id || section.type;
  return !status[key] || status[key] === "ok";
}

function makeUnit(entry, exam, type, pIdx, originalSection, section, label) {
  return {
    id: `${exam.id}:${type}:${pIdx}`,
    type,
    pIdx,
    examId: exam.id,
    exam: {
      id: exam.id,
      type: exam.type,
      year: exam.year,
      month: exam.month,
      set: exam.set,
      title: exam.title || entry.title,
      label: entry.label,
    },
    title: label || PRACTICE_TYPES[type]?.title || type,
    sectionId: originalSection.id,
    section,
  };
}

function hasContent(section) {
  if (section.type === "writing") return Boolean(section.prompt || section.directions);
  if (section.type === "translation") return Boolean(section.source);
  if (section.type === "banked-cloze") return Boolean(section.passage && (section.questions || []).length);
  if (section.type === "matching") return Boolean((section.paragraphs || []).length && (section.questions || []).length);
  return false;
}
