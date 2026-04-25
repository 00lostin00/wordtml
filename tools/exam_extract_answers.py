"""
Step 2.5 (真题流水线):从 key_*.txt 中抽取客观题答案,回填到结构化 JSON。

usage:
    python tools/exam_extract_answers.py cet6 2023-12-1
    python tools/exam_extract_answers.py cet6 2023-12-1 --write
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

ANSWER_PATTERNS = [
    re.compile(r"【\s*答案\s*】\s*([A-D])"),
    re.compile(r"(?:正确答案|答案|故选|应选)\s*(?:是|为|:|：)?\s*([A-D])"),
    re.compile(r"(?:正确答案|正确选项)\s*(?:是|为)?\s*(?:选项)?\s*([A-D])"),
    re.compile(r"(?:故|因此|所以)?\s*(?:选项)?\s*([A-D])\s*(?:项|选项)?\s*(?:为|是)?\s*正确(?:答案|选项)?"),
    re.compile(r"([A-D])\s*[)）]?\s*(?:项|选项)\s*(?:与|是|为|正确|符合|相符)"),
    re.compile(r"(?:与|故|因此|所以)\s*([A-D])\s*(?:项|选项)?\s*(?:相符|正确)"),
]


def clean_text(raw: str) -> str:
    text = PAGE_MARKER_RE.sub("\n", raw)
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def key_files(exam_type: str, slug: str) -> list[Path]:
    folder = RAW_BASE / exam_type / slug
    if not folder.exists():
        return []
    return sorted(folder.glob("key_*.txt"))


def extract_answer(block: str) -> tuple[str | None, str]:
    """返回 (answer, confidence)。只抽 A-D,不猜低置信度答案。"""
    first_line = next((line.strip() for line in block.splitlines() if line.strip()), "")
    banked = re.match(r"^([A-D])\s*[)）]\s*[^)）]{1,80}$", first_line)
    if banked and not re.search(r"[?？]", first_line):
        return banked.group(1), "high"
    for i, pattern in enumerate(ANSWER_PATTERNS):
        m = pattern.search(block)
        if m:
            return m.group(1), "high" if i < 2 else "medium"
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
    for m in Q_BLOCK_RE.finditer(clean_text(text)):
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
    return found


def collect_answers(exam_type: str, slug: str) -> dict[int, dict]:
    merged = {}
    for path in key_files(exam_type, slug):
        try:
            parsed = parse_key_text(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            parsed = parse_key_text(path.read_text(encoding="gb18030", errors="ignore"))
        for number, data in parsed.items():
            if number not in merged or merged[number]["confidence"] == "medium":
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
    ap.add_argument("type", choices=["cet6"], help="目前先支持 cet6")
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
