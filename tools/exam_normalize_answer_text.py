"""
Normalize OCR noise in already extracted answer explanations.

This only edits textual explanation/evidence fields. It does not infer or change
answer letters.

usage:
    python tools/exam_normalize_answer_text.py --all --write
    python tools/exam_normalize_answer_text.py cet6 2020-12-2 --write
"""

import argparse
import json
import sys
from pathlib import Path

from exam_extract_answers import EXAMS_BASE, iter_questions, normalize_answer_text

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def target_paths(exam_type: str | None, slug: str | None, all_targets: bool) -> list[tuple[str, str, Path]]:
    if all_targets:
        targets = []
        for typ in ("cet6", "ky1"):
            base = EXAMS_BASE / typ
            targets.extend((typ, path.stem, path) for path in sorted(base.glob("*.json")) if not path.name.startswith("_"))
        return targets
    if not exam_type or not slug:
        raise SystemExit("需要 type + slug, 或者 --all")
    return [(exam_type, slug, EXAMS_BASE / exam_type / f"{slug}.json")]


def normalize_exam(path: Path, write: bool) -> dict:
    if not path.exists():
        return {"status": "fail", "changed": 0, "reason": "exam json 不存在"}
    exam = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    touched_questions = 0
    for _section, q in iter_questions(exam):
        q_changed = False
        explanation = q.get("explanation")
        if isinstance(explanation, str) and explanation:
            normalized = normalize_answer_text(explanation)
            if normalized != explanation:
                q["explanation"] = normalized
                changed += 1
                q_changed = True
        meta = q.get("answerMeta")
        if isinstance(meta, dict):
            source_text = meta.get("sourceText")
            if isinstance(source_text, str) and source_text:
                normalized = normalize_answer_text(source_text)
                if normalized != source_text:
                    meta["sourceText"] = normalized
                    changed += 1
                    q_changed = True
        if q_changed:
            touched_questions += 1
    if write and changed:
        path.write_text(json.dumps(exam, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "ok", "changed": changed, "questions": touched_questions}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("type", nargs="?", choices=["cet6", "ky1"])
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    ok = warn = fail = 0
    for exam_type, slug, path in target_paths(args.type, args.slug, args.all):
        result = normalize_exam(path, args.write)
        if result["status"] == "fail":
            fail += 1
            print(f"FAIL  {exam_type}/{slug}  {result['reason']}")
        elif result["changed"]:
            ok += 1
            print(f"OK    {exam_type}/{slug}  fields={result['changed']} questions={result['questions']}")
        else:
            warn += 1
            print(f"SKIP  {exam_type}/{slug}  no text changes")
    print()
    print(f"汇总: OK={ok} SKIP={warn} FAIL={fail}")
    if not args.write:
        print("提示:当前是 dry-run,加 --write 才会写回 JSON")


if __name__ == "__main__":
    main()
