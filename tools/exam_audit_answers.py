"""
Audit exam answer coverage and provenance.

This does not decide that an answer is correct. It separates answers that have
traceable evidence from answers that still need review, so the UI and data work
can avoid treating inferred answers as verified standards.

usage:
    python tools/exam_audit_answers.py
    python tools/exam_audit_answers.py cet6
    python tools/exam_audit_answers.py cet6 2023-12-1

output:
    data/exams/_answer_audit_report.json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
EXAMS_BASE = ROOT / "data" / "exams"
REPORT_PATH = EXAMS_BASE / "_answer_audit_report.json"

OBJECTIVE_SECTION_TYPES = {
    "listening",
    "banked-cloze",
    "matching",
    "reading-mcq",
    "use-of-english",
    "reading-section-b",
    "cloze",
    "new-question",
}


def iter_questions(exam: dict):
    for section in exam.get("sections", []):
        for q in section.get("questions") or []:
            yield section, q
        for passage in section.get("passages") or []:
            for q in passage.get("questions") or []:
                yield section, q


def option_keys(section: dict, q: dict) -> set[str]:
    opts = q.get("options")
    if isinstance(opts, dict) and opts:
        return set(opts.keys())
    word_bank = section.get("wordBank")
    if isinstance(word_bank, dict) and word_bank:
        return set(word_bank.keys())
    paragraphs = section.get("paragraphs")
    if isinstance(paragraphs, list) and paragraphs:
        labels = set()
        for idx, paragraph in enumerate(paragraphs):
            label = paragraph.get("label") if isinstance(paragraph, dict) else None
            if label:
                labels.add(str(label).strip()[:1])
            labels.add(chr(ord("A") + idx))
        return labels
    return set()


def answer_status(section: dict, q: dict) -> tuple[str, list[str]]:
    issues = []
    answer = q.get("answer")
    if not answer:
        return "missing", ["missing-answer"]

    valid = option_keys(section, q)
    if valid and answer not in valid:
        issues.append("answer-out-of-range")

    meta = q.get("answerMeta")
    if not isinstance(meta, dict):
        return "unproven", issues + ["missing-answer-meta"]

    source_file = meta.get("sourceFile")
    source_text = meta.get("sourceText")
    confidence = meta.get("confidence")
    verified = meta.get("verified") is True

    if not source_file:
        issues.append("missing-source-file")
    if not source_text:
        issues.append("missing-source-text")
    if confidence not in {"high", "medium", "low"}:
        issues.append("missing-confidence")

    if verified:
        return "verified", issues
    if not issues and confidence == "high":
        return "key-extracted-high", ["pending-review"]
    if not issues:
        return "key-extracted-review", ["pending-review"]
    return "unproven", issues


def audit_exam(path: Path) -> dict:
    exam = json.loads(path.read_text(encoding="utf-8"))
    totals = Counter()
    issues_by_question = []
    confidence = Counter()
    source_types = Counter()

    for section, q in iter_questions(exam):
        if section.get("type") not in OBJECTIVE_SECTION_TYPES:
            continue
        totals["objective"] += 1
        status, issues = answer_status(section, q)
        totals[status] += 1
        if q.get("answer"):
            totals["answered"] += 1
        meta = q.get("answerMeta") or {}
        if meta.get("confidence"):
            confidence[meta.get("confidence")] += 1
        if meta.get("sourceType"):
            source_types[meta.get("sourceType")] += 1
        actionable = [issue for issue in issues if issue != "pending-review"]
        if actionable or status in {"unproven", "missing"}:
            issues_by_question.append({
                "section": section.get("id") or section.get("type"),
                "number": q.get("number"),
                "answer": q.get("answer"),
                "status": status,
                "issues": issues,
            })

    objective = totals["objective"]
    return {
        "type": exam.get("type"),
        "slug": path.stem,
        "id": exam.get("id"),
        "objective": objective,
        "answered": totals["answered"],
        "verified": totals["verified"],
        "keyExtractedHigh": totals["key-extracted-high"],
        "keyExtractedReview": totals["key-extracted-review"],
        "unproven": totals["unproven"],
        "missing": totals["missing"],
        "answerCoveragePct": round(totals["answered"] * 100 / objective, 1) if objective else 0,
        "verifiedCoveragePct": round(totals["verified"] * 100 / objective, 1) if objective else 0,
        "confidence": dict(confidence),
        "sourceTypes": dict(source_types),
        "issues": issues_by_question[:80],
        "issueCount": len(issues_by_question),
    }


def target_paths(exam_type: str | None, slug: str | None) -> list[Path]:
    if exam_type and slug:
        return [EXAMS_BASE / exam_type / f"{slug}.json"]
    types = [exam_type] if exam_type else ["cet6", "ky1"]
    paths = []
    for typ in types:
        folder = EXAMS_BASE / typ
        if folder.exists():
            paths.extend(path for path in sorted(folder.glob("*.json")) if not path.name.startswith("_"))
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("type", nargs="?", choices=["cet6", "ky1"], help="exam type")
    ap.add_argument("slug", nargs="?", help="target slug")
    args = ap.parse_args()

    report = {"summary": {}, "exams": []}
    summary = Counter()
    by_type = defaultdict(Counter)

    for path in target_paths(args.type, args.slug):
        if not path.exists():
            print(f"FAIL  {path} 文件不存在")
            continue
        item = audit_exam(path)
        report["exams"].append(item)
        typ = item["type"] or "unknown"
        for key in ["objective", "answered", "verified", "keyExtractedHigh", "keyExtractedReview", "unproven", "missing"]:
            summary[key] += item[key]
            by_type[typ][key] += item[key]
        print(
            f"{typ}/{item['slug']}: "
            f"answered={item['answered']}/{item['objective']} "
            f"verified={item['verified']} "
            f"unproven={item['unproven']} missing={item['missing']}"
        )

    report["summary"] = {
        "all": dict(summary),
        "byType": {typ: dict(counts) for typ, counts in by_type.items()},
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"报告: {REPORT_PATH}")


if __name__ == "__main__":
    main()
