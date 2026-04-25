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
    folder = RAW_BASE / exam_type / slug
    if not folder.exists():
        return []
    if exam_type == "ky1":
        files = list(folder.glob("key_*.txt"))
        files.extend(
            p for p in folder.glob("paper_*.txt")
            if any(k in p.name for k in ["解析", "答案", "详解", "细解"])
        )
        return sorted(set(files))
    return sorted(folder.glob("key_*.txt"))


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
    return block[:900]


def parse_key_text(text: str) -> dict[int, dict]:
    found = {}
    cleaned = clean_text(text)
    for m in Q_BLOCK_RE.finditer(cleaned):
        number = int(m.group(1))
        if not 1 <= number <= 80:
            continue
        body = m.group(2).strip()
        answer, confidence = extract_answer(body)
        if not answer:
            continue
        found[number] = {
            "answer": answer,
            "confidence": confidence,
            "explanation": trim_explanation(body),
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
            }
    return found


def _slice_loose_questions(text: str, q_min: int = 1, q_max: int = 60) -> dict:
    """OCR 文本切片:行内题号 \\b(N)\\.,每块取后续 250 字。"""
    chunks = {}
    matches = list(re.finditer(r"\b(\d{1,2})\s*\.\s+", text))
    for i, m in enumerate(matches):
        n = int(m.group(1))
        if not (q_min <= n <= q_max):
            continue
        if n in chunks:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        end = min(end, m.start() + 350)
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
                }

    for m in KY1_SIMPLE_LINE_RE.finditer(text):
        number = int(m.group(1))
        answer = m.group(2)
        if 1 <= number <= 45:
            found[number] = {
                "answer": answer,
                "confidence": "high",
                "explanation": "",
            }

    for m in KY1_INLINE_PAIR_RE.finditer(text):
        number = int(m.group(1))
        answer = m.group(2)
        if 1 <= number <= 45:
            found[number] = {
                "answer": answer,
                "confidence": "high",
                "explanation": "",
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
                        }
        for number_s, answer in KY1_SUMMARY_PAIR_RE.findall(summary):
            number = int(number_s)
            if 1 <= number <= 45 and number not in found:
                found[number] = {
                    "answer": answer,
                    "confidence": "high",
                    "explanation": "",
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
            parsed = parse_key_text(raw)
        for number, data in parsed.items():
            if number not in merged or merged[number]["confidence"] in ("medium", "low"):
                merged[number] = data | {"source": path.name}
    return merged


def iter_questions(exam: dict):
    for section in exam.get("sections", []):
        for q in section.get("questions") or []:
            yield section, q
        for passage in section.get("passages") or []:
            for q in passage.get("questions") or []:
                yield section, q


def apply_answers(exam: dict, answers: dict[int, dict]) -> dict:
    stats = {"total": 0, "filled": 0, "changed": 0, "missing": []}
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
        q["answer"] = data["answer"]
        if data.get("explanation") and not old_explanation:
            q["explanation"] = data["explanation"]
        if q.get("answer"):
            stats["filled"] += 1
        if old_answer != q.get("answer") or old_explanation != q.get("explanation", ""):
            stats["changed"] += 1
    return stats


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
    answers = collect_answers(exam_type, slug)
    if not answers:
        return {"type": exam_type, "slug": slug, "status": "warn", "issues": ["未抽到答案"]}

    exam = json.loads(path.read_text(encoding="utf-8"))
    stats = apply_answers(exam, answers)
    if write and stats["changed"]:
        path.write_text(json.dumps(exam, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = "ok" if stats["filled"] else "warn"
    issues = []
    if stats["filled"] < stats["total"]:
        issues.append(f"答案覆盖 {stats['filled']}/{stats['total']}")
    return {
        "type": exam_type,
        "slug": slug,
        "status": status,
        "answers_found": len(answers),
        "changed": stats["changed"],
        "filled": stats["filled"],
        "total": stats["total"],
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

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"汇总: OK={len(report['ok'])} WARN={len(report['warn'])} FAIL={len(report['fail'])}")
    print(f"报告: {REPORT_PATH}")
    if not args.write:
        print("提示:当前是 dry-run,加 --write 才会写回 JSON")


if __name__ == "__main__":
    main()
