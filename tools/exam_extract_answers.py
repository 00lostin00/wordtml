"""
Step 2.5 (真题流水线):从 key_*.txt 中抽取客观题答案,回填到结构化 JSON。

usage:
    python tools/exam_extract_answers.py cet6 2023-12-1
    python tools/exam_extract_answers.py ky1 2024
    python tools/exam_extract_answers.py cet6 --all --write

输出:
    data/exams/_answer_report.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
RAW_BASE = ROOT / "data" / "exams" / "_raw"
EXAMS_BASE = ROOT / "data" / "exams"
REPORT_PATH = EXAMS_BASE / "_answer_report.json"
EXTRACTOR_ID = "exam_extract_answers.py:rule-v1"

PAGE_MARKER_RE = re.compile(r"^----- PAGE \d+ -----$", re.M)
Q_BLOCK_RE = re.compile(
    r"(?ms)^\s*(?:Q\s*)?(\d{1,2})\s*[:：.．、]\s*(.*?)(?=^\s*(?:Q\s*)?\d{1,2}\s*[:：.．、]|\Z)"
)

# 高优:[答案解析] 标记后紧跟字母(段落匹配 36-45,字母 A-K)
# 中优:常见解析关键词 + 字母(听力/仔细阅读 1-25/46-55,字母 A-D)
# 答案模式按优先级排:
#   1. 段落匹配/选词的"答案解析"标记后紧跟字母(A-K / A-O)
#      OCR 噪声:中括号可能变 ［］ 【】 |) ,句号 。 经常被识别成小写 o
#   2. 选择题的常规解析关键词(A-D)
ANSWER_PATTERNS = [
    # 答案解析 + 任意 ≤12 个非大写字符(吃掉 ] ） | 换行) + 字母 + 句号或小写 o
    re.compile(r"答案\s*解析[^A-Z]{0,12}\s*([A-K])\s*(?:[。\.,]|o\b)"),
    re.compile(r"[\[［【]\s*答案\s*[\]］】]\s*([A-D])"),                          # 【答案】B
    re.compile(r"(?:正确答案|答案|故选|应选)\s*(?:是|为|:|：)?\s*([A-D])"),
    re.compile(r"(?:正确答案|正确选项)\s*(?:是|为)?\s*(?:选项)?\s*([A-D])"),
    # 选项 X ... 故为正确(/正确选项/正确答案) — 距离 ≤120 字
    re.compile(r"选项\s*([A-D])[^A-D]{0,120}?(?:为|是)?\s*正确(?:选项|答案)?"),
    # X 项 ... 故为正确 / X 选项 ... 正确(任意距离 ≤80)
    re.compile(r"\b([A-D])\s*(?:项|选项)[^A-D]{0,80}?正确(?:选项|答案)?"),
    re.compile(r"(?:故|因此|所以)?\s*(?:选项)?\s*([A-D])\s*(?:项|选项)?\s*(?:为|是)?\s*正确(?:答案|选项)?"),
    re.compile(r"([A-D])\s*[)）]?\s*(?:项|选项)\s*(?:与|是|为|正确|符合|相符)"),
    re.compile(r"(?:与|故|因此|所以)\s*([A-D])\s*(?:项|选项)?\s*(?:相符|正确)"),
    re.compile(r"由此可知\s*[，,]?\s*([A-D])\s*项"),                              # 由此可知,B 项
    # 兜底:整个 chunk 内"X 项"出现最频繁(参考 simple letter count)
]


def clean_text(raw: str) -> str:
    text = PAGE_MARKER_RE.sub("\n", raw)
    text = text.replace("\u3000", " ")
    # OCR \u628a\u7ad6\u6392"\u89e3\u6790"\u6807\u7b7e\u62c6\u6210\u5355\u5b57\u7b26\u884c(\u5355\u72ec\u4e00\u884c\u53ea\u6709"\u89e3" "\u6790" "\u89e3+" "\u6790:"\u7b49),\u6e05\u6389
    text = re.sub(r"^[ \t]*\u89e3\s*[\+\uff1b;:\uff1a]?[ \t]*$", "", text, flags=re.M)
    text = re.sub(r"^[ \t]*\u6790\s*[:\uff1a]?[ \t]*$", "", text, flags=re.M)
    text = re.sub(r"^[ \t]*\u89e3\u6790\s*[:\uff1a]?[ \t]*$", "", text, flags=re.M)
    # \u628a\u9875\u811a\u6c61\u67d3\u6e05\u6389
    text = re.sub(r"^.*?\u516d\u7ea7\s*20\d{2}.*$", "", text, flags=re.M)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def collapse_chinese_spaces(text: str) -> str:
    """OCR \u515c\u5e95:\u6298\u53e0\u4e2d\u6587\u5b57\u95f4 / \u4e2d-\u82f1\u6570\u5b57\u95f4\u88ab\u52a0\u7684\u591a\u4f59\u7a7a\u683c(\u7528\u4e8e\u7b2c\u4e8c\u8f6e\u515c\u5e95)\u3002"""
    text = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])[ \t](?=[A-Za-z0-9])", "", text)
    text = re.sub(r"(?<=[A-Za-z0-9])[ \t](?=[\u4e00-\u9fff])", "", text)
    return text


def key_files(exam_type: str, slug: str) -> list[Path]:
    folders = [RAW_BASE / exam_type / slug]
    parts = slug.split("-")
    if exam_type == "cet6" and len(parts) == 3 and parts[2].isdigit():
        folders.append(RAW_BASE / exam_type / "-".join(parts[:2]))
    existing_folders = [folder for folder in folders if folder.exists()]
    if not existing_folders:
        return []
    if exam_type == "ky1":
        files = []
        for folder in existing_folders:
            files.extend(folder.glob("key_*.txt"))
            files.extend(
                p for p in folder.glob("paper_*.txt")
                if any(k in p.name for k in ["解析", "答案", "详解", "细解"])
            )
        return sorted(set(files))
    files = []
    for folder in existing_folders:
        files.extend(folder.glob("key_*.txt"))
        files.extend(
            p for p in folder.glob("paper_*.txt")
            if any(k in p.name for k in ["答案", "解析"])
        )
    return sorted(p for p in set(files) if cet6_source_matches_slug(p, slug))


def cet6_source_matches_slug(path: Path, slug: str) -> bool:
    parts = slug.split("-")
    if len(parts) < 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        return True
    expected = (int(parts[0]), int(parts[1]))
    name = path.name
    found = re.findall(r"((?:19|20)\d{2})\s*(?:[.\-年_]\s*)?(1[0-2]|0?[1-9])\s*(?:月)?", name)
    if not found:
        return True
    return any((int(year), int(month)) == expected for year, month in found)


def ky1_aggregate_key_files(slug: str) -> list[Path]:
    """Extra KY1 answer lookup files that cover many years in one PDF/text dump."""
    if not slug or not slug.isdigit():
        return []
    year = int(slug)
    candidates: list[Path] = []

    def add_matching(folder_slug: str, start: int, end: int, *needles: str) -> None:
        if not (start <= year <= end):
            return
        folder = RAW_BASE / "ky1" / folder_slug
        if not folder.exists():
            return
        for path in folder.glob("*.txt"):
            if all(needle in path.name for needle in needles):
                candidates.append(path)

    answer_lookup = "\u7b54\u6848\u901f\u67e5"
    add_matching("2009", 1998, 2009, "1998-2009", answer_lookup)
    add_matching("2010", 2010, 2025, "2010-2025", answer_lookup)
    add_matching("2005", 2005, 2025, "2005-2025", "\u5b8c\u578b", answer_lookup)
    add_matching("2005", 2005, 2025, "2005-2025", "\u65b0\u9898\u578b", answer_lookup)
    return sorted(set(candidates))


def extract_answer(block: str) -> tuple[str | None, str]:
    """
    抽取答案字母(A-O)。返回 (answer, confidence)。
    """
    first_line = next((line.strip() for line in block.splitlines() if line.strip()), "")

    # 1. Banked-cloze 模式:首行 "D)flat" / "D) flat (adj. 平坦的)"
    banked = re.match(r"^([A-O])\s*[)）]\s*\S", first_line)
    if banked and not re.search(r"[?？]", first_line):
        if re.search(r"\([a-z]+\.|（|《|【", first_line) or len(first_line) < 30:
            return banked.group(1), "high"

    # 2. 标准模式
    for i, pattern in enumerate(ANSWER_PATTERNS):
        m = pattern.search(block)
        if m:
            return m.group(1), "high" if i < 4 else "medium"

    # 3. 兜底:把 chunk 内所有空白(含换行)塌成单空格再试一次,处理"正\n确"被换行打断的 case
    flat = re.sub(r"\s+", " ", block)
    # 修常见的中文字被换行/OCR 拆开的情况,让"正确"等关键词能成形
    flat = re.sub(r"正\s+确", "正确", flat)
    flat = re.sub(r"答\s+案", "答案", flat)
    flat = re.sub(r"选\s+项", "选项", flat)
    for pattern in ANSWER_PATTERNS:
        m = pattern.search(flat)
        if m:
            return m.group(1), "low"

    # 4. 终极兜底:扫描"X 项 + ... + 正确"或"析: 正确" 前最近的 [A-D]
    if re.search(r"析\s*[:：]?\s*正\s*确", flat):
        # 取 "析:正确" 前面 50 字内最后一个 A-D
        idx = re.search(r"析\s*[:：]?\s*正\s*确", flat).start()
        prev = flat[max(0, idx - 80):idx]
        letters = re.findall(r"([A-D])", prev)
        if letters:
            return letters[-1], "low"

    return None, "none"


def trim_explanation(block: str) -> str:
    block = re.sub(r"\s+", " ", block).strip()
    # 去掉题干和选项前缀,尽量保留解析核心。
    m = re.search(r"(?:【\s*解析\s*】|解析[:：]?|析[:：]?|解[:：]?)\s*(.+)", block)
    if m:
        block = m.group(1).strip()
    return normalize_answer_text(block)[:900]


def evidence_text(block: str, answer: str | None = None) -> str:
    """Small source snippet for auditing where an extracted answer came from."""
    text = re.sub(r"\s+", " ", block).strip()
    if not text:
        return ""
    if answer:
        idx = text.find(answer)
        if idx >= 0:
            start = max(0, idx - 120)
            end = min(len(text), idx + 180)
            return normalize_answer_text(text[start:end])
    return normalize_answer_text(text[:300])


def join_spaced_letters(match: re.Match) -> str:
    text = match.group(0)
    parts = text.split()
    if len(parts) < 3:
        return text
    # Keep compact option lists such as "A B C D" readable as choices.
    if all(part.isupper() for part in parts) and set(parts).issubset(set("ABCDEFGHIJKLMNOP")) and len(parts) <= 5:
        return " ".join(parts)
    return "".join(parts)


def normalize_answer_text(text: str) -> str:
    """Light OCR cleanup for explanations/evidence; does not infer answers."""
    if not text:
        return ""
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    replacements = {
        "〖 解 析 〗": "【解析】",
        "〖 解析 〗": "【解析】",
        "〖 精 析 〗": "【精析】",
        "［精析】": "【精析】",
        "[精析】": "【精析】",
        "（精析】": "【精析】",
        "【 精 析 】": "【精析】",
        "【 解 析 】": "【解析】",
        "题思路 〗": "【解题思路】",
        "解题思路 〗": "【解题思路】",
        "听前预测 〗": "【听前预测】",
        "语法判断 〗": "【语法判断】",
        "语义判断 〗": "【语义判断】",
        "定 位 ：": "定位：",
        "解 析 ：": "解析：",
        "精 析": "精析",
        "答 案": "答案",
        "关 键 词": "关键词",
        "关 键 信 息": "关键信息",
        "p l a c e s": "places",
        "w ith": "with",
        "fbormula": "formula",
        "0f": "of",
        "tO": "to",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    fragment_replacements = {
        r"\bd o\b": "do",
        r"\bn o\b": "no",
        r"\bo f\b": "of",
        r"\bf o r\b": "for",
        r"\bf r o m\b": "from",
        r"\bw h en\b": "when",
        r"\bw h ere\b": "where",
        r"\bw h at\b": "what",
        r"\bw ith\b": "with",
        r"\bm ost\b": "most",
        r"\bw ays\b": "ways",
        r"\bjo in in g\b": "joining",
        r"\bfi ndings\b": "findings",
        r"\bmtemat10nal\b": "international",
        r"\bM I T\b": "MIT",
        r"\bE R A\b": "ERA",
        r"\bA A P\b": "AAP",
        r"\bD N A\b": "DNA",
        r"\bG M E\b": "GME",
        r"\bA m erica\b": "America",
        r"\bW om en\b": "Women",
    }
    for pattern, new in fragment_replacements.items():
        text = re.sub(pattern, new, text)

    # Join OCR-split English words: "p l a c e s" -> "places".
    text = re.sub(r"(?<![A-Za-z])(?:[A-Za-z]\s+){2,}[A-Za-z](?![A-Za-z])", join_spaced_letters, text)

    # Remove stray spaces inside Chinese text, but keep Chinese/English readable.
    text = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])", " ", text)
    text = re.sub(r"(?<=[A-Za-z0-9])(?=[\u4e00-\u9fff])", " ", text)

    # Normalize punctuation spacing.
    text = re.sub(r"\s+([，。！？；：、）】》])", r"\1", text)
    text = re.sub(r"([（【《])\s+", r"\1", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"(?<!\d)\s*\.\s*(?!\d)", ". ", text)
    text = re.sub(r"(?<=\d), (?=\d)", ",", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\. (?=[）】])", ".", text)
    return text


def source_kind(path: Path, aggregate_paths: set[Path]) -> str:
    if path in aggregate_paths:
        return "aggregate-key"
    if "OCR" in path.name.upper():
        return "ocr-key"
    return "official-key"


SOURCE_PRIORITY = {
    "official-key": 3,
    "aggregate-key": 2,
    "ocr-key": 1,
}

CONFIDENCE_PRIORITY = {
    "high": 3,
    "medium": 2,
    "low": 1,
}


def answer_priority(data: dict) -> tuple[int, int]:
    return (
        SOURCE_PRIORITY.get(data.get("sourceType", "official-key"), 0),
        CONFIDENCE_PRIORITY.get(data.get("confidence", "low"), 0),
    )


SET_WORD_TO_NUMBER = {
    "一": 1,
    "二": 2,
    "三": 3,
    "1": 1,
    "2": 2,
    "3": 3,
}

CET6_SET_MARKER_RE = re.compile(r"第\s*([一二三123])\s*套")
CET6_EXPLICIT_ANSWER_RE = re.compile(
    r"(?:锁定\s*答案|正确\s*答案|答案\s*精\s*析|答案)\s*[\]】）):：\s]*[\[【(（]?\s*([A-O])\s*[\]】)）]?",
    re.I,
)
CET6_EXPLANATION_HEAD_RE = re.compile(
    r"(?<![A-Za-z])([A-P])\s*[)）]\s*(?:[〖【\[\(（［]\s*)?(?:精\s*析|解析|详解|定位|考点|语法判断|语义判断)",
    re.I,
)
CET6_CHOICE_CORRECT_RE = re.compile(
    r"([A-D])\s*(?:项|选项)[^A-D]{0,90}?(?:正确|符合|对应|直接)",
    re.I,
)
CET6_INLINE_ANSWER_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s*(?:题)?\s*([A-O])\s*(?:项|[)）])",
    re.I,
)
CET6_NUMBERED_ANSWER_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s*[.．、,，]\s*([A-P0O])\s*[)）]",
    re.I,
)
CET6_COMPACT_ANSWER_RE = re.compile(r"(?<![\dA-Za-z])(\d{1,2})\s*([A-D])(?=[\s\u4e00-\u9fff])")
CET6_SUMMARY_RANGE_RE = re.compile(r"【\s*(\d{1,2})\s*[-~—–]\s*(\d{1,2})\s*】\s*([A-O]+)")
CET6_HEADING_ANSWER_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s*[.．、·]\s*([A-P])\s*(?:[)）])?\s*(?:[〖【\[]\s*)?(?:解\s*题\s*思\s*路|解\s*析|精\s*析|定\s*位|语\s*法\s*判\s*断|语\s*义\s*判\s*断)",
    re.I,
)


def cet6_set_number(slug: str | None) -> int | None:
    if not slug:
        return None
    parts = slug.split("-")
    if len(parts) == 3 and parts[2] in {"1", "2", "3"}:
        return int(parts[2])
    return None


def slice_cet6_set_text(text: str, slug: str | None) -> str:
    """When one OCR dump contains all three CET6 sets, keep only the requested set."""
    set_number = cet6_set_number(slug)
    if not set_number:
        return text
    markers = [
        (m.start(), SET_WORD_TO_NUMBER.get(m.group(1)))
        for m in CET6_SET_MARKER_RE.finditer(text)
    ]
    markers = [marker for marker in markers if marker[1]]
    if not markers:
        return text

    for i, (start, number) in enumerate(markers):
        if number != set_number:
            continue
        end = len(text)
        for next_start, next_number in markers[i + 1:]:
            if next_number != number:
                end = next_start
                break
        return text[start:end]
    return text


def cet6_answer_allowed(number: int, answer: str) -> bool:
    answer = answer.upper()
    if 26 <= number <= 35:
        return "A" <= answer <= "O"
    if 36 <= number <= 45:
        return "A" <= answer <= "P"
    return "A" <= answer <= "D"


def parse_cet6_chunk_answer(body: str, number: int) -> tuple[str | None, str]:
    m = CET6_NUMBERED_ANSWER_RE.search(body)
    if m and int(m.group(1)) == number:
        answer = "O" if m.group(2) == "0" else m.group(2).upper()
        if cet6_answer_allowed(number, answer):
            return answer, "high"

    m = CET6_EXPLICIT_ANSWER_RE.search(body)
    if m and cet6_answer_allowed(number, m.group(1)):
        return m.group(1).upper(), "high"

    m = CET6_EXPLANATION_HEAD_RE.search(body)
    if m and cet6_answer_allowed(number, m.group(1)):
        return m.group(1).upper(), "high"

    m = CET6_CHOICE_CORRECT_RE.search(body)
    if m and cet6_answer_allowed(number, m.group(1)):
        return m.group(1).upper(), "medium"

    answer, confidence = extract_answer(body)
    if answer and cet6_answer_allowed(number, answer):
        return answer.upper(), confidence

    return None, "none"


def parse_cet6_ocr_answers(text: str) -> dict[int, dict]:
    """Extra CET6 parser for OCR dumps that preserve answer markers but not clean blocks."""
    found = {}
    cleaned = collapse_chinese_spaces(clean_text(text))

    for number, body in iter_loose_question_chunks(cleaned, q_max=55, limit=2200):
        if number in found:
            continue
        answer, confidence = parse_cet6_chunk_answer(body, number)
        if not answer:
            continue
        found[number] = {
            "answer": answer,
            "confidence": confidence,
            "explanation": trim_explanation(body),
            "evidence": evidence_text(body, answer),
        }

    flat = re.sub(r"\s+", " ", cleaned)
    for pattern, confidence in (
        (CET6_INLINE_ANSWER_RE, "medium"),
        (CET6_NUMBERED_ANSWER_RE, "medium"),
        (CET6_COMPACT_ANSWER_RE, "low"),
    ):
        for m in pattern.finditer(flat):
            number = int(m.group(1))
            answer = "O" if m.group(2) == "0" else m.group(2).upper()
            if not 1 <= number <= 55 or number in found:
                continue
            if not cet6_answer_allowed(number, answer):
                continue
            start = max(0, m.start() - 220)
            end = min(len(flat), m.end() + 260)
            snippet = flat[start:end]
            if confidence == "low" and not re.search(r"Q\s*\d|问题|答案|题|选项|听|阅读", snippet):
                continue
            found[number] = {
                "answer": answer,
                "confidence": confidence,
                "explanation": "",
                "evidence": evidence_text(snippet, answer),
            }

    return found


def parse_cet6_summary_answers(text: str) -> dict[int, dict]:
    found = {}
    for m in CET6_SUMMARY_RANGE_RE.finditer(text):
        start = int(m.group(1))
        end = int(m.group(2))
        letters = list(m.group(3).upper())
        if end < start or len(letters) < end - start + 1:
            continue
        for offset, answer in enumerate(letters[:end - start + 1]):
            number = start + offset
            if not 1 <= number <= 55 or not cet6_answer_allowed(number, answer):
                continue
            found[number] = {
                "answer": answer,
                "confidence": "high",
                "explanation": "",
                "evidence": evidence_text(m.group(0), answer),
                "verified": True,
                "verification": "official-answer-summary",
            }
    return found


def parse_cet6_heading_answers(text: str) -> dict[int, dict]:
    found = {}
    flat = re.sub(r"\s+", " ", collapse_chinese_spaces(clean_text(text)))
    for m in CET6_HEADING_ANSWER_RE.finditer(flat):
        number = int(m.group(1))
        answer = m.group(2).upper()
        if not 1 <= number <= 55 or not cet6_answer_allowed(number, answer):
            continue
        start = max(0, m.start() - 180)
        end = min(len(flat), m.end() + 280)
        snippet = flat[start:end]
        found[number] = {
            "answer": answer,
            "confidence": "high",
            "explanation": "",
            "evidence": evidence_text(snippet, answer),
        }
    return found


def iter_loose_question_chunks(text: str, q_min: int = 1, q_max: int = 60, limit: int = 350):
    matches = list(re.finditer(r"(?<!\d)(?:Q\s*)?(\d{1,2}|[lI])\s*[.．、,，:：·•]\s+", text))
    for i, m in enumerate(matches):
        token = m.group(1)
        n = 1 if token in {"l", "I"} else int(token)
        if not (q_min <= n <= q_max):
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        end = min(end, m.start() + limit)
        yield n, text[m.start():end]


def parse_key_text(text: str) -> dict[int, dict]:
    found = {}
    cleaned = clean_text(text)
    found.update(parse_cet6_summary_answers(cleaned))
    for number, data in parse_cet6_heading_answers(cleaned).items():
        found.setdefault(number, data)
    for m in Q_BLOCK_RE.finditer(cleaned):
        number = int(m.group(1))
        if not 1 <= number <= 80 or number in found:
            continue
        body = m.group(2).strip()
        answer, confidence = extract_answer(body)
        if not answer:
            continue
        found[number] = {
            "answer": answer,
            "confidence": confidence,
            "explanation": trim_explanation(body),
            "evidence": evidence_text(body, answer),
        }

    # OCR 兜底 1:Windows OCR 把每个汉字之间加空格 + 行被合并成长行,
    # 标准切片切不出。把空格折叠后再扫一遍。
    collapsed = collapse_chinese_spaces(cleaned)
    if collapsed != cleaned:
        for m in Q_BLOCK_RE.finditer(collapsed):
            number = int(m.group(1))
            if not 1 <= number <= 80 or number in found:
                continue
            body = m.group(2).strip()
            answer, confidence = extract_answer(body)
            if not answer:
                continue
            found[number] = {
                "answer": answer,
                "confidence": "low",
                "explanation": trim_explanation(body),
                "evidence": evidence_text(body, answer),
            }

    # OCR 兜底 2:题号不在行首,直接行内扫描 \b(\d+)\.,
    # 取后续 250 字 chunk。用"答案/故选/正确"关键词过滤假阳性。
    if collapsed != cleaned:
        chunks = _slice_loose_questions(collapsed)
        for number, body in chunks.items():
            if number in found:
                continue
            if not re.search(r"答案|故\s*选|正确|【\s*[A-K]\s*】", body):
                continue   # 没答案信号,跳过
            answer, _ = extract_answer(body)
            if not answer:
                continue
            found[number] = {
                "answer": answer,
                "confidence": "low",
                "explanation": trim_explanation(body),
                "evidence": evidence_text(body, answer),
            }

    for number, data in parse_cet6_ocr_answers(cleaned).items():
        if number not in found or found[number]["confidence"] in ("medium", "low"):
            found[number] = data
    return found


def _slice_loose_questions(text: str, q_min: int = 1, q_max: int = 60, limit: int = 350) -> dict:
    """OCR 文本切片:行内题号 \\b(N)\\.,每块取后续 250 字。"""
    chunks = {}
    matches = list(re.finditer(r"(?<!\d)(?:Q\s*)?(\d{1,2}|[lI])\s*[.．、,，:：·•]\s+", text))
    for i, m in enumerate(matches):
        token = m.group(1)
        n = 1 if token in {"l", "I"} else int(token)
        if not (q_min <= n <= q_max):
            continue
        if n in chunks:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        end = min(end, m.start() + limit)
        chunks[n] = text[m.start():end]
    return chunks


def normalize_ky1_text(text: str) -> str:
    text = clean_text(text)
    pairs = {
        "［": "[", "【": "[", "〔": "[", "］": "]", "】": "]", "〕": "]",
        "．": ".", "。": ".", "、": ".", "：": ":", "—": "-", "→": "-",
        "Ｔ": "T", "ｔ": "t",
    }
    for old, new in pairs.items():
        text = text.replace(old, new)
    return text


KY1_DIRECT_PATTERNS = [
    re.compile(r"(?m)^\s*(\d{1,2})\s*\.\s*\[\s*([A-G])\s*\]"),
    re.compile(r"(?m)^\s*(\d{1,2})\s*\.\s*\[\s*答案\s*\]\s*([A-G])"),
    re.compile(r"(?m)^\s*(\d{1,2})\s*\.\s*答案\s*[:：]?\s*([A-G])"),
    re.compile(r"(?m)^\s*(\d{1,2})\s*\.\s*正确答案\s*[:：]?\s*([A-G])"),
]

KY1_SUMMARY_RE = re.compile(r"(?:答案汇总|答案速查|参考答案|正确答案)[\s\S]{0,900}")
KY1_SUMMARY_PAIR_RE = re.compile(r"(\d{1,2})\s*\.?\s*([A-G])\b")
KY1_SUMMARY_RANGE_RE = re.compile(r"(\d{1,2})\s*[-~～—至到]\s*(\d{1,2})\s*([A-G](?:\s*[A-G]){1,19})")
KY1_SIMPLE_LINE_RE = re.compile(r"(?m)^\s*(\d{1,2})\s*[.\u3001\uff0e]\s*([A-G])\s*$")
KY1_INLINE_PAIR_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[.\u3001\uff0e\uff1a:,\uff0c\u00b7]\s*([A-G])\b")
KY1_OCR_AMP_PAIR_RE = re.compile(r"(?<!\d)3\s*&\s*([A-G])\b")
KY1_YEAR_MARKER_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*\u5e74")


def slice_ky1_year_text(text: str, slug: str | None) -> str:
    if not slug or not slug.isdigit():
        return text
    target_year = int(slug)
    markers = list(KY1_YEAR_MARKER_RE.finditer(text))
    if not markers:
        return text

    segments = []
    for i, marker in enumerate(markers):
        if int(marker.group(1)) != target_year:
            continue
        start = max(0, marker.start() - 350)
        end = len(text)
        if i + 1 < len(markers):
            end = max(marker.end(), markers[i + 1].start() - 350)
        segment = text[start:end]
        simple_answers = len(KY1_SIMPLE_LINE_RE.findall(segment))
        inline_answers = len(KY1_INLINE_PAIR_RE.findall(segment))
        summary_answers = len(KY1_SUMMARY_PAIR_RE.findall(segment))
        segments.append((simple_answers + inline_answers + summary_answers, len(segment), segment))

    if not segments:
        return text
    segments.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return segments[0][2]


def parse_ky1_key_text(text: str, slug: str | None = None) -> dict[int, dict]:
    """从考研英语一解析文本中抽 1-45 客观题答案。"""
    text = normalize_ky1_text(text)
    text = slice_ky1_year_text(text, slug)
    found = {}

    for pattern in KY1_DIRECT_PATTERNS:
        for m in pattern.finditer(text):
            number = int(m.group(1))
            answer = m.group(2)
            if 1 <= number <= 45:
                found[number] = {
                    "answer": answer,
                    "confidence": "high",
                    "explanation": ky1_explanation_after(text, m.end()),
                    "evidence": evidence_text(text[m.start():m.end() + 300], answer),
                }

    for m in KY1_SIMPLE_LINE_RE.finditer(text):
        number = int(m.group(1))
        answer = m.group(2)
        if 1 <= number <= 45:
            found[number] = {
                "answer": answer,
                "confidence": "high",
                "explanation": "",
                "evidence": evidence_text(m.group(0), answer),
            }

    for m in KY1_INLINE_PAIR_RE.finditer(text):
        number = int(m.group(1))
        answer = m.group(2)
        if 1 <= number <= 45:
            found[number] = {
                "answer": answer,
                "confidence": "high",
                "explanation": "",
                "evidence": evidence_text(m.group(0), answer),
            }

    inline_tokens = [
        (m.start(), int(m.group(1)), m.group(2))
        for m in KY1_INLINE_PAIR_RE.finditer(text)
        if 1 <= int(m.group(1)) <= 45
    ]
    for m in KY1_OCR_AMP_PAIR_RE.finditer(text):
        answer = m.group(1)
        prev = next((token for token in reversed(inline_tokens) if token[0] < m.start()), None)
        nxt = next((token for token in inline_tokens if token[0] > m.end()), None)
        number = None
        if prev and nxt and prev[1] == 37 and nxt[1] == 39:
            number = 38
        elif prev and nxt and prev[1] == 39 and nxt[1] == 41:
            number = 38
        elif prev and nxt and prev[1] == 30 and nxt[1] == 40:
            number = 35
        if number:
            found[number] = {
                "answer": answer,
                "confidence": "high",
                "explanation": "",
                "evidence": evidence_text(m.group(0), answer),
            }

    for m in KY1_SUMMARY_RE.finditer(text):
        summary = m.group(0)
        for start_s, end_s, letters_s in KY1_SUMMARY_RANGE_RE.findall(summary):
            start, end = int(start_s), int(end_s)
            letters = re.findall(r"[A-G]", letters_s)
            if end >= start and len(letters) >= end - start + 1:
                for offset, answer in enumerate(letters[:end - start + 1]):
                    number = start + offset
                    if 1 <= number <= 45 and number not in found:
                        found[number] = {
                            "answer": answer,
                            "confidence": "high",
                            "explanation": "",
                            "evidence": evidence_text(summary, answer),
                        }
        for number_s, answer in KY1_SUMMARY_PAIR_RE.findall(summary):
            number = int(number_s)
            if 1 <= number <= 45 and number not in found:
                found[number] = {
                    "answer": answer,
                    "confidence": "high",
                    "explanation": "",
                    "evidence": evidence_text(summary, answer),
                }

    # 逐题细解常见:"故 A 项正确" / "C 项正确" 出现在题号 chunk 内。
    for m in Q_BLOCK_RE.finditer(text):
        number = int(m.group(1))
        if not 1 <= number <= 45 or number in found:
            continue
        body = m.group(2).strip()
        answer, confidence = extract_ky1_answer_from_block(body)
        if answer:
            found[number] = {
                "answer": answer,
                "confidence": confidence,
                "explanation": trim_explanation(body),
                "evidence": evidence_text(body, answer),
            }

    return found


def extract_ky1_answer_from_block(block: str) -> tuple[str | None, str]:
    patterns = [
        re.compile(r"(?:故|所以|因此)?\s*([A-G])\s*(?:项|选项)\s*(?:正确|为正确答案|是正确答案)"),
        re.compile(r"(?:正确答案|答案|应选|故选)\s*(?:是|为|:)?\s*([A-G])"),
        re.compile(r"([A-G])\s*(?:项|选项)[^A-G]{0,80}?(?:符合|正确|最佳)"),
    ]
    flat = re.sub(r"\s+", " ", block)
    for i, pattern in enumerate(patterns):
        m = pattern.search(flat)
        if m:
            return m.group(1), "medium" if i else "high"
    return None, "none"


def ky1_explanation_after(text: str, start: int) -> str:
    tail = text[start:start + 1200]
    tail = re.split(r"\n\s*\d{1,2}\s*\.", tail, maxsplit=1)[0]
    return trim_explanation(tail)


def collect_answers(exam_type: str, slug: str) -> dict[int, dict]:
    merged = {}
    aggregate_paths = ky1_aggregate_key_files(slug) if exam_type == "ky1" else []
    paths = aggregate_paths + key_files(exam_type, slug)
    aggregate_set = set(aggregate_paths)
    for path in paths:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = path.read_text(encoding="gb18030", errors="ignore")
        if exam_type == "ky1":
            parsed = parse_ky1_key_text(raw, slug if path in aggregate_set else None)
        else:
            cet6_text = raw if path.parent.name == slug else slice_cet6_set_text(raw, slug)
            parsed = parse_key_text(cet6_text)
        for number, data in parsed.items():
            enriched = data | {
                "source": path.name,
                "sourceFile": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sourceType": source_kind(path, aggregate_set),
                "extractor": EXTRACTOR_ID,
            }
            if number not in merged or answer_priority(enriched) > answer_priority(merged[number]):
                merged[number] = enriched
    return merged


def iter_questions(exam: dict):
    for section in exam.get("sections", []):
        for q in section.get("questions") or []:
            yield section, q
        for passage in section.get("passages") or []:
            for q in passage.get("questions") or []:
                yield section, q


def make_answer_meta(data: dict) -> dict:
    return {
        "sourceType": data.get("sourceType", "official-key"),
        "sourceFile": data.get("sourceFile") or data.get("source", ""),
        "sourceText": data.get("evidence", ""),
        "extractor": data.get("extractor", EXTRACTOR_ID),
        "confidence": data.get("confidence", "medium"),
        "verified": data.get("verified") is True,
        "verification": data.get("verification", "pending-review"),
    }


def can_replace_existing_answer(old_meta: dict, new_data: dict) -> bool:
    if old_meta.get("verified") is True:
        return False
    if new_data.get("sourceType") == "official-key":
        return True
    old_source_type = old_meta.get("sourceType")
    new_source_type = new_data.get("sourceType")
    old_source_file = old_meta.get("sourceFile")
    new_source_file = new_data.get("sourceFile") or new_data.get("source")
    if old_source_type == new_source_type == "ocr-key" and old_source_file == new_source_file:
        old_conf = CONFIDENCE_PRIORITY.get(old_meta.get("confidence", "low"), 0)
        new_conf = CONFIDENCE_PRIORITY.get(new_data.get("confidence", "low"), 0)
        return new_conf >= old_conf
    return False


def apply_answers(exam: dict, answers: dict[int, dict]) -> dict:
    stats = {
        "total": 0,
        "filled": 0,
        "changed": 0,
        "missing": [],
        "locked": 0,
        "conflicts": [],
        "confidence": {"high": 0, "medium": 0, "low": 0},
    }
    for _section, q in iter_questions(exam):
        number = q.get("number")
        if not isinstance(number, int):
            continue
        stats["total"] += 1
        data = answers.get(number)
        if not data:
            stats["missing"].append(number)
            continue
        old_answer = q.get("answer")
        old_explanation = q.get("explanation", "")
        old_meta = q.get("answerMeta") or {}
        if old_answer and old_answer != data["answer"]:
            if not can_replace_existing_answer(old_meta, data):
                stats["locked"] += 1
                stats["conflicts"].append({
                    "number": number,
                    "existingAnswer": old_answer,
                    "extractedAnswer": data["answer"],
                    "sourceFile": data.get("sourceFile") or data.get("source", ""),
                    "verified": old_meta.get("verified") is True,
                })
                if q.get("answer"):
                    stats["filled"] += 1
                continue
        q["answer"] = data["answer"]
        if data.get("explanation") and not old_explanation:
            q["explanation"] = data["explanation"]
        q["answerMeta"] = make_answer_meta(data)
        confidence = q["answerMeta"].get("confidence", "medium")
        if confidence in stats["confidence"]:
            stats["confidence"][confidence] += 1
        if q.get("answer"):
            stats["filled"] += 1
        if old_answer != q.get("answer") or old_explanation != q.get("explanation", "") or old_meta != q.get("answerMeta"):
            stats["changed"] += 1
    return stats


def clear_mismatched_cet6_answers(exam: dict, slug: str) -> int:
    cleared = 0
    for _section, q in iter_questions(exam):
        meta = q.get("answerMeta") or {}
        source_file = meta.get("sourceFile") or ""
        if not q.get("answer") or "data/exams/_raw/cet6/" not in source_file:
            continue
        if cet6_source_matches_slug(Path(source_file), slug):
            continue
        q["answer"] = None
        q.pop("answerMeta", None)
        cleared += 1
    return cleared


def target_paths(exam_type: str, slug: str | None, all_targets: bool) -> list[tuple[str, Path]]:
    if all_targets:
        base = EXAMS_BASE / exam_type
        return [(path.stem, path) for path in sorted(base.glob("*.json")) if not path.name.startswith("_")]
    if not slug:
        raise SystemExit("需要 slug,或者使用 --all")
    return [(slug, EXAMS_BASE / exam_type / f"{slug}.json")]


def run_target(exam_type: str, slug: str, path: Path, write: bool) -> dict:
    if not path.exists():
        return {"type": exam_type, "slug": slug, "status": "fail", "issues": ["exam json 不存在"]}
    exam = json.loads(path.read_text(encoding="utf-8"))
    stale_cleared = clear_mismatched_cet6_answers(exam, slug) if exam_type == "cet6" else 0
    answers = collect_answers(exam_type, slug)
    stats = apply_answers(exam, answers)
    if write and (stats["changed"] or stale_cleared):
        path.write_text(json.dumps(exam, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = "ok" if stats["filled"] else "warn"
    issues = []
    if not answers:
        issues.append("未抽到答案")
    if stats["filled"] < stats["total"]:
        issues.append(f"答案覆盖 {stats['filled']}/{stats['total']}")
    if stale_cleared:
        issues.append(f"清理错年月旧答案 {stale_cleared} 题")
    if stats["locked"]:
        issues.append(f"已有答案冲突 {stats['locked']} 题,已跳过自动覆盖")
    if stats["conflicts"]:
        issues.append(f"答案冲突待人工复核 {len(stats['conflicts'])} 题")
    return {
        "type": exam_type,
        "slug": slug,
        "status": status,
        "answers_found": len(answers),
        "changed": stats["changed"] + stale_cleared,
        "filled": stats["filled"],
        "total": stats["total"],
        "confidence": stats["confidence"],
        "locked": stats["locked"],
        "conflicts": stats["conflicts"],
        "issues": issues,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("type", choices=["cet6", "ky1"], help="真题类型")
    ap.add_argument("slug", nargs="?", help="目标 slug")
    ap.add_argument("--all", action="store_true", help="处理全部")
    ap.add_argument("--write", action="store_true", help="写回 JSON")
    args = ap.parse_args()

    report = {"ok": [], "warn": [], "fail": []}
    for slug, path in target_paths(args.type, args.slug, args.all):
        result = run_target(args.type, slug, path, args.write)
        report[result["status"]].append(result)
        print(f"{result['status'].upper():4}  {args.type}/{slug}  "
              f"{result.get('filled', 0)}/{result.get('total', 0)} "
              f"changed={result.get('changed', 0)}")
        for issue in result.get("issues", []):
            print(f"  • {issue}")

    type_report_path = EXAMS_BASE / f"_answer_report_{args.type}.json"
    type_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"汇总: OK={len(report['ok'])} WARN={len(report['warn'])} FAIL={len(report['fail'])}")
    print(f"报告: {type_report_path}")
    if not args.write:
        print("提示:当前是 dry-run,加 --write 才会写回 JSON")


if __name__ == "__main__":
    main()
