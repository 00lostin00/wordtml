"""
Step 2 (真题流水线):把 _raw/*.txt 解析成结构化 JSON。

当前覆盖:CET-6 paper(Writing / Listening / Reading × 3 sections / Translation)
答案 + 解析在 Step 2.5 单独从 key 文件抽,这里 answer/explanation 字段先留空。

usage:
    python tools/exam_parse.py cet6 2023-12-1     # 解析单卷
    python tools/exam_parse.py cet6 --all         # 解析 cet6 全部 paper
    python tools/exam_parse.py cet6 2023-12-1 --debug   # 输出中间步骤

输出:
    data/exams/cet6/<slug>.json
    data/exams/_parse_report.json   # 解析问题汇总
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
RAW_BASE = ROOT / "data" / "exams" / "_raw"
OUT_BASE = ROOT / "data" / "exams"


# ============================================================
# 通用文本清理
# ============================================================

PAGE_MARKER_RE = re.compile(r"^----- PAGE \d+ -----$", re.M)
PAGE_NUM_RE = re.compile(r"^\s*\d{1,3}\s*$", re.M)

# 多种页眉/页脚污染模式(按需扩充):
#   ·2023年12月六级真题(第一套)·         ← 老格式,带中点
#   2024 年12 月英语六级真题第2 套         ← 新格式,空格分隔
#   2024 年12 月英语六级真题第2 套  第7 页，共9 页
#   六级 2023.12 | 第T              ← OCR 污染的页脚,T 实为"一"
#   六级2023.12 ;第一套
HEADER_PATTERNS = [
    re.compile(r"·\s*20\d{2}\s*年\s*\d{1,2}\s*月.*?(?:真题|六级|四级).*?·"),
    re.compile(r"^.*?20\d{2}\s*年\s*\d{1,2}\s*月.*?(?:真题|六级|四级).*?第\s*\d+\s*[套页].*$", re.M),
    re.compile(r"^\s*第\s*\d+\s*页\s*[，,]\s*共\s*\d+\s*页.*$", re.M),
    re.compile(r"^\s*(?:四级|六级)\s*20\d{2}[\.\s]\d{1,2}.*$", re.M),
    re.compile(r"^\s*20\d{2}\s*年\s*\d{1,2}\s*月.*?(?:六级|四级).*$", re.M),
]


def clean_text(raw: str) -> str:
    """去掉 page 标记 / 页脚 / 页眉污染 / 单独行的页码,统一空白。"""
    t = PAGE_MARKER_RE.sub("\n", raw)
    for pat in HEADER_PATTERNS:
        t = pat.sub("", t)
    t = PAGE_NUM_RE.sub("", t)
    # 多空行折叠
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# ============================================================
# Section 切分
# ============================================================

# Part 锚点:支持 ASCII (I, II, III, IV) 和 Unicode 罗马数字 (Ⅰ, Ⅱ, Ⅲ, Ⅳ)
PART_RE = re.compile(
    r"^\s*Part\s+([A-ZⅠⅡⅢⅣ]{1,4})\s*\n+\s*([A-Z][A-Za-z ]+?)\s*\n",
    re.M,
)

# 名称归一(原始 OCR 有时把 II 抽成 I,所以靠后续标题判断)
PART_TITLE_TO_ID = {
    "Writing": "writing",
    "Listening Comprehension": "listening",
    "Reading Comprehension": "reading",
    "Translation": "translation",
}


def split_parts(text: str) -> dict:
    """返回 {section_id: text_block}。"""
    cleaned = clean_text(text)
    matches = list(PART_RE.finditer(cleaned))
    parts = {}
    for i, m in enumerate(matches):
        title = m.group(2).strip()
        section_id = PART_TITLE_TO_ID.get(title)
        if not section_id:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        parts[section_id] = cleaned[start:end].strip()
    return parts


# ============================================================
# Writing
# ============================================================

DIRECTIONS_RE = re.compile(r"Directions\s*[:：]\s*(.+?)(?=\n\n|$)", re.S)


def parse_writing(block: str) -> dict:
    directions_match = DIRECTIONS_RE.search(block)
    directions = re.sub(r"\s+", " ", directions_match.group(1).strip()) if directions_match else ""
    # 题面常见模式:"begins with the sentence "..."" 或 "based on the picture..."
    quote_m = re.search(r'sentence\s*[“"](.+?)[”"]', block, re.S)
    prompt = re.sub(r"\s+", " ", quote_m.group(1).strip()) if quote_m else ""
    return {
        "id": "writing",
        "type": "writing",
        "title": "Part I Writing",
        "minutes": 30,
        "directions": directions,
        "prompt": prompt,
    }


# ============================================================
# Listening
# ============================================================

# 题号 + 选项 A 的起头:"1.A)" / "1 A)" / "1. A)"
Q_A_LINE = re.compile(r"^\s*(\d{1,2})\s*[\.、]?\s*A\)\s*(.+?)\s*$", re.M)
# 单独 B/C/D 行
OPT_LINE = re.compile(r"^\s*([B-D])\)\s*(.+?)\s*$", re.M)


def parse_listening(block: str) -> dict:
    """
    Listening 切 section A/B/C 三段,每段抽问题 + 4 选项。
    paper 里没有听力原文 / 答案,这两项留空,后续从 key 补。
    """
    # 找 "Section A/B/C" 标记,但 listening 部分不是必须分 section,我们抽所有题
    questions = parse_mcq_questions(block, q_range=(1, 25))

    return {
        "id": "listening",
        "type": "listening",
        "title": "Part II Listening Comprehension",
        "minutes": 30,
        "questions": questions,
    }


def parse_mcq_questions(block: str, q_range: Optional[tuple] = None) -> list:
    """
    通用选择题抽取。处理:
      1. "1.A) ...\nB) ...\nC) ...\nD) ..."  单列布局
      2. "1.A) ...\nC) ...\nB) ...\nD) ..."  两列布局(顺序是 A,C,B,D)
      3. 题干横跨多行

    返回: [{number, stem, options: {A,B,C,D}}, ...]

    "stem" 在 paper 听力部分往往不存在(只有选项),这种情况 stem 留空。
    """
    questions = []
    lines = block.split("\n")
    n_lines = len(lines)

    i = 0
    while i < n_lines:
        line = lines[i]
        # 题号 + A)
        m = re.match(r"^\s*(\d{1,3})\s*[\.、]?\s*A\)\s*(.+?)\s*$", line)
        if not m:
            i += 1
            continue

        qnum = int(m.group(1))
        if q_range and not (q_range[0] <= qnum <= q_range[1]):
            i += 1
            continue

        # 收集后续 3 个选项行
        opt_a_text = m.group(2).strip()
        collected = {"A": opt_a_text}
        order = ["A"]
        j = i + 1
        while j < n_lines and len(collected) < 4:
            opt_m = re.match(r"^\s*([B-D])\)\s*(.+?)\s*$", lines[j])
            if not opt_m:
                # 题干续行?跨行选项续行?简化处理:停
                # 可能这一行是空行,也可能下一题已开始
                if re.match(r"^\s*\d{1,3}\s*[\.、]?\s*A\)", lines[j]):
                    break
                j += 1
                continue
            letter = opt_m.group(1)
            text = opt_m.group(2).strip()
            collected[letter] = text
            order.append(letter)
            j += 1

        if len(collected) < 4:
            # 可能选项跨页/解析,跳过
            i = j if j > i else i + 1
            continue

        # 检测两列布局:期望 A,B,C,D 顺序;实际可能是 A,C,B,D
        # 规则:如果 order == [A,C,B,D],说明是两列读出来的,选项已经按 letter dict 收齐,无需重排
        # (我们不依赖 order,只依赖 letter→text 字典)

        questions.append({
            "id": f"q{qnum}",
            "number": qnum,
            "stem": "",  # listening: paper 不含问题文本
            "options": {
                "A": collected.get("A", ""),
                "B": collected.get("B", ""),
                "C": collected.get("C", ""),
                "D": collected.get("D", ""),
            },
            "answer": None,
            "explanation": "",
        })
        i = j

    return questions


# ============================================================
# Reading
# ============================================================

def parse_reading(block: str) -> list:
    """
    切 Section A / B / C,分别解析。
    """
    # Section 锚点
    sect_re = re.compile(r"^\s*Section\s+([ABC])\s*$", re.M)
    matches = list(sect_re.finditer(block))
    sections = []
    for i, m in enumerate(matches):
        letter = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        sect_block = block[start:end].strip()
        if letter == "A":
            sections.append(parse_banked_cloze(sect_block))
        elif letter == "B":
            sections.append(parse_matching(sect_block))
        elif letter == "C":
            sections.append(parse_reading_mcq(sect_block))
    return sections


def parse_banked_cloze(block: str) -> dict:
    """
    Section A 选词填空:passage 含 [26]-[35] 编号空,后跟 word bank A)-O)。
    """
    # word bank: 每行 "A) word" 形式;最后一行可能无尾换行
    bank_match = re.search(
        r"((?:^[A-O]\)\s*\S[^\n]*(?:\n|$)){5,})",
        block, re.M,
    )
    word_bank = {}
    bank_block = ""
    if bank_match:
        bank_block = bank_match.group(1)
        for line in bank_block.split("\n"):
            mm = re.match(r"^([A-O])\)\s*(\S.*)$", line.strip())
            if mm:
                word_bank[mm.group(1)] = mm.group(2).strip()

    # passage = block 去掉 word bank
    passage = block
    if bank_match:
        passage = block[:bank_match.start()].strip()

    # 直接用 passage 原文,_25_ / [26] 等空位保留
    questions = []
    for n in range(26, 36):
        questions.append({
            "id": f"q{n}",
            "number": n,
            "answer": None,
            "explanation": "",
        })

    return {
        "id": "reading-banked",
        "type": "banked-cloze",
        "title": "Section A · 选词填空",
        "passage": passage,
        "wordBank": word_bank,
        "questions": questions,
    }


def parse_matching(block: str) -> dict:
    """
    Section B 段落匹配:多段 A)-K) 标号段落 + 36-45 题陈述。
    """
    # 段落: 行首 "A)" "B)" ... 标号 —— OCR 偶尔把 "I)" 误识成 "1)",一并接受
    para_re = re.compile(r"^\s*([A-K1])\)\s*(.+?)(?=^\s*[A-K1]\)|\Z)", re.M | re.S)
    paragraphs = []
    para_text_block = block
    # 找题目区(36-45 题),允许题号后无空格
    q_start_m = re.search(r"^\s*36\.\s*[A-Z]", block, re.M)
    if q_start_m:
        para_text_block = block[:q_start_m.start()]
        questions_block = block[q_start_m.start():]
    else:
        questions_block = ""

    for m in para_re.finditer(para_text_block):
        label = m.group(1)
        if label == "1":
            label = "I"  # OCR 把 I) 识成 1)
        paragraphs.append({
            "label": label,
            "text": m.group(2).strip(),
        })

    # 题目: "36.内容..." 或 "36. 内容..."
    questions = []
    q_re = re.compile(r"^(\d{2})\.\s*(.+?)(?=^\d{2}\.\s*[A-Z]|\Z)", re.M | re.S)
    for m in q_re.finditer(questions_block):
        n = int(m.group(1))
        if 36 <= n <= 45:
            questions.append({
                "id": f"q{n}",
                "number": n,
                "stem": m.group(2).strip(),
                "answer": None,
                "explanation": "",
            })

    return {
        "id": "reading-matching",
        "type": "matching",
        "title": "Section B · 段落匹配",
        "paragraphs": paragraphs,
        "questions": questions,
    }


def parse_reading_mcq(block: str) -> dict:
    """
    Section C 仔细阅读:Passage One/Two,每篇配 5 题。
    """
    # 切 Passage One / Passage Two
    psg_split = re.split(r"^\s*Pass\S*\s+(One|Two|Three)\s*$", block, flags=re.M)
    passages = []
    if len(psg_split) >= 3:
        # 切完是 [前缀, 'One', body1, 'Two', body2, ...]
        for i in range(1, len(psg_split), 2):
            label = "Passage " + psg_split[i]
            body = psg_split[i + 1] if i + 1 < len(psg_split) else ""
            passages.append({"label": label, "body": body.strip()})
    else:
        passages = [{"label": "Passage", "body": block}]

    out_passages = []
    for psg in passages:
        body = psg["body"]
        # 找 questions 起始(46/51 等题号),允许 . 后无空格
        q_start_m = re.search(r"^\s*\d{2}\.\s*[A-Z]", body, re.M)
        if q_start_m:
            text = body[:q_start_m.start()].strip()
            qblock = body[q_start_m.start():]
        else:
            text = body.strip()
            qblock = ""

        # 用稳健方式:先按题号切大块,再每块抽选项
        questions_dict = []
        chunks = re.split(r"(?=^\d{2}\.\s*[A-Z])", qblock, flags=re.M)
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            # 题干到第一个 ? 或换行 + A) 之前
            head = re.match(r"^(\d{2})\.\s*(.+?)(?=\n\s*A\))", chunk, re.S)
            if not head:
                continue
            n = int(head.group(1))
            stem = head.group(2).strip().replace("\n", " ")
            # 同一行可能两个选项挤一起(如 "B) ... D) ..."),先 normalize:
            #   如果 [ABCD]) 前面是空格 + 字母 + 空格(说明在行中而非行首),插入换行
            chunk_norm = re.sub(r"(?<=\S)(\s+)([A-D])\)", lambda m: "\n" + m.group(2) + ")", chunk)
            opts = {}
            for letter in "ABCD":
                m = re.search(
                    rf"^\s*{letter}\)\s*(.+?)(?=^\s*[ABCD]\)|^\s*\d{{2}}\.\s*[A-Z]|\Z)",
                    chunk_norm, re.M | re.S,
                )
                if m:
                    opts[letter] = m.group(1).strip().replace("\n", " ")
            if len(opts) >= 4:
                questions_dict.append({
                    "id": f"q{n}",
                    "number": n,
                    "stem": stem,
                    "options": opts,
                    "answer": None,
                    "explanation": "",
                })

        out_passages.append({
            "label": psg["label"],
            "text": text,
            "questions": questions_dict,
        })

    return {
        "id": "reading-mcq",
        "type": "reading-mcq",
        "title": "Section C · 仔细阅读",
        "passages": out_passages,
    }


# ============================================================
# Translation
# ============================================================

def parse_translation(block: str) -> dict:
    # Directions 单独抽:从 "Directions:" 到 "Answer Sheet" 那行结束
    dir_match = re.search(
        r"Directions\s*[:：]\s*(.+?Answer Sheet[^\n]*)",
        block, re.S,
    )
    directions = dir_match.group(1).strip() if dir_match else ""
    # 中文段落:整个 block 里找含中文的行,拼起来(去掉 directions 部分)
    cn_lines = [l.strip() for l in block.split("\n") if re.search(r"[一-鿿]", l)]
    source = "".join(cn_lines)
    return {
        "id": "translation",
        "type": "translation",
        "title": "Part IV Translation",
        "minutes": 30,
        "directions": directions,
        "source": source,
        "reference": "",
        "explanation": "",
    }


# ============================================================
# 主流程
# ============================================================

def parse_cet6_paper(text: str, slug: str) -> dict:
    parts = split_parts(text)
    # 拆解 reading 子节为多个 section
    sections = []
    if "writing" in parts:
        sections.append(parse_writing(parts["writing"]))
    if "listening" in parts:
        sections.append(parse_listening(parts["listening"]))
    if "reading" in parts:
        sections.extend(parse_reading(parts["reading"]))
    if "translation" in parts:
        sections.append(parse_translation(parts["translation"]))

    # slug → 元数据
    parts_slug = slug.split("-")
    year = int(parts_slug[0]) if parts_slug and parts_slug[0].isdigit() else 0
    month = int(parts_slug[1]) if len(parts_slug) > 1 and parts_slug[1].isdigit() else 0
    set_n = int(parts_slug[2]) if len(parts_slug) > 2 and parts_slug[2].isdigit() else 0

    return {
        "id": f"cet6-{slug}",
        "type": "cet6",
        "year": year,
        "month": month,
        "set": set_n,
        "title": f"{year}年{month}月大学英语六级真题(第{set_n or 1}套)",
        "sections": sections,
    }


# ============================================================
# KY1 (考研英语一)
# ============================================================

SECTION_MARK_RE = re.compile(r"^\s*(Section\s+[IVX]+|Part\s+[ABC])\s*$", re.M)


def slice_between(text: str, start_pat: str, end_pat: str | None = None) -> str:
    start = re.search(start_pat, text, re.M | re.I)
    if not start:
        return ""
    if end_pat:
        end = re.search(end_pat, text[start.end():], re.M | re.I)
        if end:
            return text[start.end():start.end() + end.start()].strip()
    return text[start.end():].strip()


def parse_option_rows(block: str, numbers: range) -> dict:
    """处理 [A]/[B] 按列 OCR 的选项列表。"""
    opts = {n: {} for n in numbers}
    counters = {letter: 0 for letter in "ABCD"}
    current_number = None
    current_letter = None
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"^(?:(\d{1,2})\s*[.．、])?\s*\[\s*([A-D])\s*\]\s*(.+)$", line)
        if m:
            number_s, letter, value = m.groups()
            if number_s:
                number = int(number_s)
                counters[letter] = list(numbers).index(number) + 1 if number in numbers else counters[letter] + 1
            else:
                counters[letter] += 1
                number = list(numbers)[counters[letter] - 1] if counters[letter] <= len(list(numbers)) else None
            if number in opts:
                opts[number][letter] = value.strip()
                current_number = number
                current_letter = letter
            continue
        if current_number in opts and current_letter:
            opts[current_number][current_letter] = (opts[current_number][current_letter] + " " + line).strip()
    return opts


def parse_ky_cloze(block: str) -> dict:
    opt_start = re.search(r"^\s*1\s*[.．、]?\s*\[\s*A\s*\]", block, re.M)
    passage = block[:opt_start.start()].strip() if opt_start else block.strip()
    option_block = block[opt_start.start():] if opt_start else ""
    options = parse_option_rows(option_block, range(1, 21))
    questions = []
    for n in range(1, 21):
        questions.append({
            "id": f"q{n}",
            "number": n,
            "stem": f"Blank {n}",
            "options": {k: options.get(n, {}).get(k, "") for k in "ABCD"},
            "answer": None,
            "explanation": "",
        })
    return {
        "id": "cloze",
        "type": "reading-mcq",
        "title": "Section I · Use of English",
        "minutes": 15,
        "passages": [{"label": "Use of English", "text": passage, "questions": questions}],
    }


def parse_ky_reading_part_a(block: str) -> dict:
    passages = []
    matches = list(re.finditer(r"^\s*Text\s+([1-4])\s*$", block, re.M))
    for idx, m in enumerate(matches):
        label = f"Text {m.group(1)}"
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        text_block = block[start:end].strip()
        q_start = re.search(r"^\s*(\d{2})\s*[.．、]", text_block, re.M)
        passage_text = text_block[:q_start.start()].strip() if q_start else text_block
        q_block = text_block[q_start.start():] if q_start else ""
        question_matches = list(re.finditer(r"(?ms)^\s*(\d{2})\s*[.．、]\s*(.*?)(?=^\s*\d{2}\s*[.．、]|\Z)", q_block))
        questions = []
        for qm in question_matches:
            number = int(qm.group(1))
            body = qm.group(2).strip()
            opt_start = re.search(r"^\s*\[\s*A\s*\]", body, re.M)
            stem = body[:opt_start.start()].strip() if opt_start else body
            opts = {}
            for om in re.finditer(r"(?ms)^\s*\[\s*([A-D])\s*\]\s*(.*?)(?=^\s*\[\s*[A-D]\s*\]|\Z)", body[opt_start.start():] if opt_start else ""):
                opts[om.group(1)] = re.sub(r"\s+", " ", om.group(2)).strip()
            if 21 <= number <= 40:
                questions.append({
                    "id": f"q{number}",
                    "number": number,
                    "stem": re.sub(r"\s+", " ", stem),
                    "options": {k: opts.get(k, "") for k in "ABCD"},
                    "answer": None,
                    "explanation": "",
                })
        passages.append({"label": label, "text": passage_text, "questions": questions})
    return {
        "id": "reading-mcq",
        "type": "reading-mcq",
        "title": "Section II Part A · Reading Comprehension",
        "minutes": 70,
        "passages": passages,
    }


def parse_ky_part_b(block: str) -> dict:
    labels = {}
    option_start = re.search(r"^\s*\[\s*A\s*\]", block, re.M)
    body = block[:option_start.start()].strip() if option_start else block.strip()
    option_block = block[option_start.start():] if option_start else ""
    for om in re.finditer(r"(?ms)^\s*\[\s*([A-G])\s*\]\s*(.*?)(?=^\s*\[\s*[A-G]\s*\]|\Z)", option_block):
        labels[om.group(1)] = re.sub(r"\s+", " ", om.group(2)).strip()

    q_matches = list(re.finditer(r"(?ms)^\s*\((4[1-5])\)\s*([A-Za-z][^\n]*)\n(.*?)(?=^\s*\(4[1-5]\)|\Z)", body))
    questions = []
    paragraphs = []
    for qm in q_matches:
        number = int(qm.group(1))
        name = qm.group(2).strip()
        text = qm.group(3).strip()
        paragraphs.append({"label": str(number), "text": f"{name}\n{text}"})
        questions.append({"id": f"q{number}", "number": number, "stem": name, "answer": None, "explanation": ""})
    return {
        "id": "new-question",
        "type": "matching",
        "title": "Section II Part B · New Question Type",
        "minutes": 15,
        "paragraphs": [{"label": k, "text": v} for k, v in sorted(labels.items())] or paragraphs,
        "questions": questions,
    }


def parse_ky_translation(block: str) -> dict:
    return {
        "id": "translation",
        "type": "translation",
        "title": "Section II Part C · Translation",
        "minutes": 20,
        "targetLanguage": "zh",
        "directions": "Translate the underlined segments into Chinese.",
        "source": block.strip(),
    }


def parse_ky_writing(block: str) -> list:
    part_a = slice_between(block, r"^\s*Part\s+A\s*$", r"^\s*Part\s+B\s*$")
    part_b = slice_between(block, r"^\s*Part\s+B\s*$")
    return [
        {
            "id": "writing-1",
            "type": "writing",
            "title": "Section III Part A · Writing",
            "minutes": 20,
            "directions": part_a.strip(),
            "prompt": "",
        },
        {
            "id": "writing-2",
            "type": "writing",
            "title": "Section III Part B · Writing",
            "minutes": 40,
            "directions": part_b.strip(),
            "prompt": "",
        },
    ]


def parse_ky1_paper(text: str, slug: str) -> dict:
    cleaned = clean_text(text)
    cloze = slice_between(cleaned, r"^\s*Section\s+I\b.*$", r"^\s*Section\s+II\b.*$")
    reading_all = slice_between(cleaned, r"^\s*Section\s+II\b.*$", r"^\s*Section\s+III\b.*$")
    part_a = slice_between(reading_all, r"^\s*Part\s+A\s*$", r"^\s*Part\s+B\s*$")
    part_b = slice_between(reading_all, r"^\s*Part\s+B\s*$", r"^\s*Part\s+C\s*$")
    part_c = slice_between(reading_all, r"^\s*Part\s+C\s*$")
    writing = slice_between(cleaned, r"^\s*Section\s+III\b.*$")

    year = int(slug) if slug.isdigit() else 0
    sections = []
    if cloze:
        sections.append(parse_ky_cloze(cloze))
    if part_a:
        sections.append(parse_ky_reading_part_a(part_a))
    if part_b:
        sections.append(parse_ky_part_b(part_b))
    if part_c:
        sections.append(parse_ky_translation(part_c))
    if writing:
        sections.extend(parse_ky_writing(writing))

    return {
        "id": f"ky1-{slug}",
        "type": "ky1",
        "year": year,
        "month": 12,
        "set": 1,
        "title": f"{year}年考研英语一真题",
        "sections": sections,
    }


def find_paper_text(slug_dir: Path, slug: str = "") -> Optional[Path]:
    """slug 目录下挑一个 paper_*.txt。优先选文件名匹配 slug 年/月的,再挑最大的。"""
    candidates = sorted(slug_dir.glob("paper_*.txt"), key=lambda p: p.stat().st_size, reverse=True)
    if not candidates:
        return None
    parts = slug.split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        year, month = parts[0], parts[1]
        # 多种文件名月份写法
        kws = [
            f"{year}.{month}",
            f"{year}-{month}",
            f"{year}.{int(month)}",
            f"{year}-{int(month)}",
            f"{year}年{int(month)}月",
            f"{year}年{month}月",
        ]
        for kw in kws:
            for p in candidates:
                if kw in p.name:
                    return p
    searchable = [p for p in candidates if "可复制搜索查词" in p.name]
    if searchable:
        return searchable[0]
    return candidates[0]


def parse_one(type_: str, slug: str, debug: bool = False) -> dict:
    slug_dir = RAW_BASE / type_ / slug
    paper_path = find_paper_text(slug_dir, slug)
    if not paper_path:
        raise FileNotFoundError(f"找不到 paper:{slug_dir}")
    text = paper_path.read_text(encoding="utf-8")

    if type_ == "cet6":
        result = parse_cet6_paper(text, slug)
    elif type_ == "ky1":
        result = parse_ky1_paper(text, slug)
    else:
        raise NotImplementedError(f"暂未支持类型:{type_}")

    out_dir = OUT_BASE / type_
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if debug:
        # 输出每节的概览
        print(f"sections: {len(result['sections'])}")
        for s in result["sections"]:
            n_q = len(s.get("questions", []))
            if "passages" in s:
                n_q = sum(len(p.get("questions", [])) for p in s["passages"])
            elif "paragraphs" in s:
                n_q = len(s.get("questions", []))
            print(f"  - {s['id']:30s} type={s['type']:14s} ({n_q} 题)")

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("type", choices=["cet6", "ky1"], help="类型")
    ap.add_argument("slug", nargs="?", help="目标 slug,如 2023-12-1")
    ap.add_argument("--all", action="store_true", help="解析该类型所有 paper")
    ap.add_argument("--debug", action="store_true", help="打印解析详情")
    args = ap.parse_args()

    if args.all:
        type_dir = RAW_BASE / args.type
        slugs = [p.name for p in sorted(type_dir.iterdir()) if p.is_dir()]
        if args.type == "ky1":
            slugs = [s for s in slugs if s.isdigit()]
        report = {"ok": [], "fail": []}
        for slug in slugs:
            try:
                r = parse_one(args.type, slug, debug=False)
                n_sections = len(r["sections"])
                print(f"OK  {args.type}/{slug:12s}  ({n_sections} sections)")
                report["ok"].append({"slug": slug, "sections": n_sections})
            except Exception as e:
                print(f"ERR {args.type}/{slug:12s}  {e}")
                report["fail"].append({"slug": slug, "err": str(e)})
        report_path = OUT_BASE / "_parse_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告:{report_path}")
    else:
        if not args.slug:
            ap.error("需要 slug 或 --all")
        result = parse_one(args.type, args.slug, debug=args.debug)
        print(f"OK -> {OUT_BASE / args.type / (args.slug + '.json')}")


if __name__ == "__main__":
    main()
