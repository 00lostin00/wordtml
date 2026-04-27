"""
Review and lock extracted exam answers.

The extractor writes answerMeta.verified=false. This tool is the explicit gate
for turning a traceable extracted answer into a locked, reviewed answer.

usage:
    python tools/exam_verify_answers.py queue cet6 --limit 200
    python tools/exam_verify_answers.py verify cet6 2023-12-1 1 2 3 --reviewer alice
    python tools/exam_verify_answers.py set cet6 2023-12-1 1 B --reviewer alice --note "checked against key PDF"

outputs:
    data/exams/_answer_review_queue.jsonl
    data/exams/_answer_review_queue.md
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
EXAMS_BASE = ROOT / "data" / "exams"
QUEUE_JSONL = EXAMS_BASE / "_answer_review_queue.jsonl"
QUEUE_MD = EXAMS_BASE / "_answer_review_queue.md"
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_exam(exam_type: str, slug: str) -> tuple[dict, Path]:
    path = EXAMS_BASE / exam_type / f"{slug}.json"
    if not path.exists():
        raise SystemExit(f"exam json 不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8")), path


def save_exam(path: Path, exam: dict) -> None:
    path.write_text(json.dumps(exam, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_questions(exam: dict):
    for section in exam.get("sections", []):
        for q in section.get("questions") or []:
            yield section, q
        for passage in section.get("passages") or []:
            for q in passage.get("questions") or []:
                yield section, q


def find_question(exam: dict, number: int) -> tuple[dict, dict]:
    for section, q in iter_questions(exam):
        if q.get("number") == number:
            return section, q
    raise SystemExit(f"找不到题号: {number}")


def valid_answer_keys(section: dict, q: dict) -> set[str]:
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
            if isinstance(paragraph, dict) and paragraph.get("label"):
                labels.add(str(paragraph["label"]).strip()[:1])
            labels.add(chr(ord("A") + idx))
        return labels
    return set()


def ensure_meta(q: dict) -> dict:
    meta = q.get("answerMeta")
    if not isinstance(meta, dict):
        meta = {
            "sourceType": "manual",
            "sourceFile": "",
            "sourceText": "",
            "extractor": "manual-review",
            "confidence": "high",
            "verified": False,
            "verification": "pending-review",
        }
        q["answerMeta"] = meta
    return meta


def mark_verified(q: dict, reviewer: str, note: str = "") -> None:
    meta = ensure_meta(q)
    meta["verified"] = True
    meta["verification"] = "manual-review"
    meta["verifiedAt"] = now_iso()
    meta["verifiedBy"] = reviewer
    if note:
        meta["reviewNote"] = note


def mark_auto_verified(q: dict, method: str, note: str = "") -> None:
    meta = ensure_meta(q)
    meta["verified"] = True
    meta["verification"] = method
    meta["verifiedAt"] = now_iso()
    meta["verifiedBy"] = "codex-auto"
    if note:
        meta["reviewNote"] = note


def strong_evidence_match(q: dict, answer: str) -> bool:
    meta = q.get("answerMeta") or {}
    evidence = re.sub(r"\s+", "", meta.get("sourceText") or "")
    if not evidence:
        return False
    answer = re.escape(answer)
    number = q.get("number")
    patterns = [
        rf"(?:正确答案|参考答案|答案|故选|应选|答案为|答案是)[:：]?\s*{answer}",
        rf"{answer}(?:项|选项)?(?:正确|相符|符合|为正确答案|为答案)",
        rf"(?:选项|故|因此|所以){answer}(?:项|选项)?(?:正确|相符|符合)",
        rf"[\[【（(]{answer}[\]】）)]",
    ]
    if number is not None:
        patterns.extend([
            rf"{int(number)}[.、．:：]?{answer}\b",
            rf"{int(number)}[.、．:：]?\[{answer}\]",
        ])
    return any(re.search(pattern, evidence, flags=re.I) for pattern in patterns)


def evidence_answer_candidates(q: dict, valid: set[str]) -> list[str]:
    meta = q.get("answerMeta") or {}
    evidence = re.sub(r"\s+", "", meta.get("sourceText") or "")
    if not evidence:
        return []
    candidates = []
    patterns = [
        r"(?:正确答案|参考答案|答案|故选|应选|答案为|答案是|锁定答案)[\]】）):：]?([A-O])",
        r"([A-O])[\]】）)]?(?:【精析】|【解析】|〖精析〗|〖解析〗|详解|精析)",
        r"(?:故|因此|所以)[^A-O]{0,20}答案为([A-O])",
        r"正确项([A-O])",
        r"([A-O])(?:项|选项)?(?:正确|相符|符合|为正确答案|为答案)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, evidence, flags=re.I):
            value = match.group(1).upper()
            if not valid or value in valid:
                candidates.append(value)
    return sorted(set(candidates))


def is_auto_verifiable(section: dict, q: dict, min_confidence: str, include_ocr: bool) -> tuple[bool, str, str | None]:
    answer = q.get("answer")
    if not answer:
        return False, "missing-answer", None
    valid = valid_answer_keys(section, q)
    if valid and answer not in valid:
        return False, "answer-out-of-range", None
    meta = q.get("answerMeta") or {}
    if meta.get("verified") is True:
        return False, "already-verified", None
    source_type = meta.get("sourceType")
    if source_type == "ocr-key" and not include_ocr:
        return False, "ocr-disabled", None
    if source_type not in {"official-key", "aggregate-key", "ocr-key"}:
        return False, "unsupported-source", None
    confidence = meta.get("confidence")
    if CONFIDENCE_RANK.get(confidence, -1) < CONFIDENCE_RANK[min_confidence]:
        return False, "low-confidence", None
    if not meta.get("sourceFile") or not meta.get("sourceText"):
        return False, "missing-source", None
    candidates = evidence_answer_candidates(q, valid)
    if len(candidates) == 1:
        if candidates[0] != answer:
            return False, "evidence-answer-conflict", candidates[0]
        return True, "auto-strict-source", candidates[0]
    if len(candidates) > 1:
        return False, "ambiguous-evidence", None
    if not strong_evidence_match(q, answer):
        return False, "weak-evidence", None
    return True, "auto-strict-source", answer


def command_verify(args) -> None:
    exam, path = load_exam(args.type, args.slug)
    changed = 0
    for number_s in args.numbers:
        number = int(number_s)
        _section, q = find_question(exam, number)
        if not q.get("answer"):
            print(f"SKIP q{number}: 没有 answer,不能核验")
            continue
        mark_verified(q, args.reviewer, args.note or "")
        changed += 1
        print(f"VERIFIED {args.type}/{args.slug} q{number} = {q.get('answer')}")
    if changed and not args.dry_run:
        save_exam(path, exam)
    elif changed:
        print("dry-run: 未写回")


def command_set(args) -> None:
    exam, path = load_exam(args.type, args.slug)
    section, q = find_question(exam, int(args.number))
    answer = args.answer.strip().upper()
    valid = valid_answer_keys(section, q)
    if valid and answer not in valid:
        raise SystemExit(f"答案 {answer} 不在可选范围: {sorted(valid)}")
    q["answer"] = answer
    if args.explanation is not None:
        q["explanation"] = args.explanation
    meta = ensure_meta(q)
    meta["sourceType"] = "manual"
    meta["sourceFile"] = args.source_file or meta.get("sourceFile", "")
    meta["sourceText"] = args.source_text or meta.get("sourceText", "")
    meta["extractor"] = "manual-review"
    meta["confidence"] = "high"
    mark_verified(q, args.reviewer, args.note or "")
    if not args.dry_run:
        save_exam(path, exam)
    print(f"SET+VERIFIED {args.type}/{args.slug} q{args.number} = {answer}")


def command_auto(args) -> None:
    types = [args.type] if args.type else ["cet6", "ky1"]
    summary = {"checked": 0, "verified": 0, "skipped": {}}
    for exam_type in types:
        folder = EXAMS_BASE / exam_type
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            if path.name.startswith("_"):
                continue
            exam = json.loads(path.read_text(encoding="utf-8"))
            changed = 0
            for section, q in iter_questions(exam):
                if not q.get("answer"):
                    continue
                summary["checked"] += 1
                ok, reason, candidate = is_auto_verifiable(section, q, args.min_confidence, args.include_ocr)
                if ok:
                    mark_auto_verified(q, reason, "strict source/evidence/option-range check")
                    summary["verified"] += 1
                    changed += 1
                elif reason == "evidence-answer-conflict" and args.fix_conflicts and candidate:
                    old_answer = q.get("answer")
                    q["answer"] = candidate
                    mark_auto_verified(q, "auto-strict-corrected", f"corrected extracted answer {old_answer} -> {candidate}")
                    summary["verified"] += 1
                    summary["corrected"] = summary.get("corrected", 0) + 1
                    changed += 1
                else:
                    summary["skipped"][reason] = summary["skipped"].get(reason, 0) + 1
            if changed and not args.dry_run:
                save_exam(path, exam)
            if changed:
                print(f"AUTO  {exam_type}/{path.stem}  verified={changed}")
    print()
    print(f"checked={summary['checked']} auto_verified={summary['verified']} corrected={summary.get('corrected', 0)}")
    for reason, count in sorted(summary["skipped"].items(), key=lambda item: item[0]):
        print(f"skip {reason}: {count}")
    if args.dry_run:
        print("dry-run: 未写回")


def question_row(exam: dict, slug: str, section: dict, q: dict) -> dict:
    meta = q.get("answerMeta") or {}
    opts = q.get("options") or {}
    return {
        "type": exam.get("type"),
        "slug": slug,
        "examId": exam.get("id"),
        "title": exam.get("title"),
        "section": section.get("id") or section.get("type"),
        "number": q.get("number"),
        "stem": q.get("stem", ""),
        "options": opts,
        "answer": q.get("answer"),
        "explanation": q.get("explanation", ""),
        "sourceType": meta.get("sourceType"),
        "sourceFile": meta.get("sourceFile"),
        "sourceText": meta.get("sourceText"),
        "confidence": meta.get("confidence"),
        "verified": meta.get("verified") is True,
        "verification": meta.get("verification"),
    }


def queue_sort_key(row: dict):
    return (
        row["verified"],
        CONFIDENCE_RANK.get(row.get("confidence"), -1),
        row.get("type") or "",
        row.get("slug") or "",
        row.get("number") or 0,
    )


def command_queue(args) -> None:
    rows = []
    types = [args.type] if args.type else ["cet6", "ky1"]
    for exam_type in types:
        folder = EXAMS_BASE / exam_type
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            if path.name.startswith("_"):
                continue
            exam = json.loads(path.read_text(encoding="utf-8"))
            for section, q in iter_questions(exam):
                if not q.get("answer"):
                    continue
                meta = q.get("answerMeta") or {}
                if args.pending_only and meta.get("verified") is True:
                    continue
                rows.append(question_row(exam, path.stem, section, q))

    rows.sort(key=queue_sort_key)
    if args.limit:
        rows = rows[:args.limit]

    QUEUE_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    QUEUE_MD.write_text(render_markdown(rows), encoding="utf-8")
    print(f"queue rows: {len(rows)}")
    print(f"JSONL: {QUEUE_JSONL}")
    print(f"Markdown: {QUEUE_MD}")


def render_markdown(rows: list[dict]) -> str:
    lines = [
        "# Answer Review Queue",
        "",
        "Only mark a row verified after checking the answer against its source evidence.",
        "",
    ]
    for row in rows:
        lines.append(f"## {row['type']}/{row['slug']} q{row['number']} · {row.get('confidence') or 'unknown'}")
        lines.append("")
        lines.append(f"- Exam: {row.get('title') or row.get('examId')}")
        lines.append(f"- Section: {row.get('section')}")
        lines.append(f"- Answer: `{row.get('answer')}`")
        lines.append(f"- Source: `{row.get('sourceFile') or ''}`")
        lines.append(f"- Verify command: `python tools/exam_verify_answers.py verify {row['type']} {row['slug']} {row['number']} --reviewer <name>`")
        if row.get("stem"):
            lines.append("")
            lines.append("Stem:")
            lines.append("")
            lines.append(f"> {row['stem'][:500]}")
        if row.get("options"):
            lines.append("")
            lines.append("Options:")
            for key, value in sorted(row["options"].items()):
                lines.append(f"- `{key}` {value}")
        if row.get("sourceText"):
            lines.append("")
            lines.append("Evidence:")
            lines.append("")
            lines.append(f"> {row['sourceText'][:900]}")
        lines.append("")
    return "\n" + "\n".join(lines).strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    queue = sub.add_parser("queue", help="export pending review queue")
    queue.add_argument("type", nargs="?", choices=["cet6", "ky1"], help="optional exam type")
    queue.add_argument("--limit", type=int, default=0, help="limit exported rows")
    queue.add_argument("--pending-only", action=argparse.BooleanOptionalAction, default=True)
    queue.set_defaults(func=command_queue)

    auto = sub.add_parser("auto", help="strictly auto-verify answers with strong source evidence")
    auto.add_argument("type", nargs="?", choices=["cet6", "ky1"], help="optional exam type")
    auto.add_argument("--min-confidence", choices=["high", "medium", "low"], default="medium")
    auto.add_argument("--include-ocr", action="store_true", help="allow OCR key snippets too")
    auto.add_argument("--fix-conflicts", action="store_true", help="correct answers when evidence has one clear different answer")
    auto.add_argument("--dry-run", action="store_true")
    auto.set_defaults(func=command_auto)

    verify = sub.add_parser("verify", help="mark existing answers verified")
    verify.add_argument("type", choices=["cet6", "ky1"])
    verify.add_argument("slug")
    verify.add_argument("numbers", nargs="+")
    verify.add_argument("--reviewer", required=True)
    verify.add_argument("--note", default="")
    verify.add_argument("--dry-run", action="store_true")
    verify.set_defaults(func=command_verify)

    set_answer = sub.add_parser("set", help="set/correct one answer and mark it verified")
    set_answer.add_argument("type", choices=["cet6", "ky1"])
    set_answer.add_argument("slug")
    set_answer.add_argument("number")
    set_answer.add_argument("answer")
    set_answer.add_argument("--reviewer", required=True)
    set_answer.add_argument("--note", default="")
    set_answer.add_argument("--explanation")
    set_answer.add_argument("--source-file", default="")
    set_answer.add_argument("--source-text", default="")
    set_answer.add_argument("--dry-run", action="store_true")
    set_answer.set_defaults(func=command_set)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
