"""
Step 3 (真题流水线):校验 exam_parse.py 产出的 JSON。

usage:
    python tools/exam_validate.py cet6 2023-12-1     # 校验单卷
    python tools/exam_validate.py cet6 --all          # 校验所有 cet6 已生成的卷
    python tools/exam_validate.py --all               # 校验所有类型

输出:
    控制台:每卷状态(OK / WARN / FAIL)+ 问题清单
    data/exams/_validation_report.json
"""

import argparse
import json
import sys
from pathlib import Path

# Windows 控制台默认 GBK,强制 stdout UTF-8 输出避免中文报错
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
EXAMS_BASE = ROOT / "data" / "exams"
REPORT_PATH = EXAMS_BASE / "_validation_report.json"

# CET-6 标准结构
CET6_EXPECTED = {
    "sections": [
        ("writing",         {"min_chars": 30}),
        ("listening",       {"questions": 25}),
        ("reading-banked",  {"questions": 10, "word_bank": 15}),
        ("reading-matching",{"questions": 10, "paragraphs_min": 9}),
        ("reading-mcq",     {"questions": 10, "passages_min": 2}),
        ("translation",     {"min_source_chars": 80}),
    ],
}

# 考研英语一(占位,Step 2 还没实现 ky1 解析,先放规则)
KY1_EXPECTED = {
    "sections": [
        ("writing-1",     {}),  # 应用文/小作文
        ("writing-2",     {}),  # 大作文
        ("cloze",         {"questions": 20}),
        ("reading-mcq",   {"questions": 20, "passages_min": 4}),
        ("new-question",  {"questions": 5}),
        ("translation",   {}),
    ],
}

EXPECTED_BY_TYPE = {
    "cet6": CET6_EXPECTED,
    "ky1":  KY1_EXPECTED,
}


def count_questions(section: dict) -> int:
    if "questions" in section:
        return len(section["questions"])
    if "passages" in section:
        return sum(len(p.get("questions", [])) for p in section["passages"])
    return 0


def validate_section(section: dict, rule: dict) -> list:
    """返回该 section 的问题清单(空 = 通过)。"""
    issues = []
    sid = section.get("id", "?")
    typ = section.get("type", "?")

    # 问题数
    if "questions" in rule:
        actual = count_questions(section)
        expected = rule["questions"]
        if actual != expected:
            issues.append(f"[{sid}] 题数 {actual} ≠ {expected}")

    # word bank
    if "word_bank" in rule:
        actual = len(section.get("wordBank", {}))
        expected = rule["word_bank"]
        if actual != expected:
            issues.append(f"[{sid}] wordBank {actual}/{expected}")

    # 段落数下限
    if "paragraphs_min" in rule:
        actual = len(section.get("paragraphs", []))
        if actual < rule["paragraphs_min"]:
            issues.append(f"[{sid}] paragraphs {actual} < {rule['paragraphs_min']}")

    # passages 数下限
    if "passages_min" in rule:
        actual = len(section.get("passages", []))
        if actual < rule["passages_min"]:
            issues.append(f"[{sid}] passages {actual} < {rule['passages_min']}")

    # writing prompt / directions 长度
    if "min_chars" in rule:
        chars = len(section.get("prompt", "")) + len(section.get("directions", ""))
        if chars < rule["min_chars"]:
            issues.append(f"[{sid}] prompt+directions 太短 ({chars}<{rule['min_chars']})")

    # translation source 长度
    if "min_source_chars" in rule:
        chars = len(section.get("source", ""))
        if chars < rule["min_source_chars"]:
            issues.append(f"[{sid}] source 中文过短 ({chars}<{rule['min_source_chars']})")

    # 选择题:每题必有 4 选项
    questions = section.get("questions") or []
    if "passages" in section:
        for p in section["passages"]:
            questions.extend(p.get("questions", []))
    for q in questions:
        opts = q.get("options")
        if opts is None:
            continue  # banked-cloze / matching 没选项,正常
        if len(opts) != 4 or any(not v for v in opts.values()):
            issues.append(f"[{sid}] q{q.get('number')} 选项不全:{list(opts.keys())}")

    return issues


def validate_exam(exam: dict) -> list:
    typ = exam.get("type", "")
    rules = EXPECTED_BY_TYPE.get(typ)
    if not rules:
        return [f"未知 exam type: {typ}"]

    sections_by_id = {s["id"]: s for s in exam.get("sections", [])}
    issues = []
    for sid, rule in rules["sections"]:
        if sid not in sections_by_id:
            issues.append(f"[{sid}] section 缺失")
            continue
        issues.extend(validate_section(sections_by_id[sid], rule))

    # 答案覆盖率
    total_q = 0
    answered = 0
    for s in exam.get("sections", []):
        for q in (s.get("questions") or []):
            total_q += 1
            if q.get("answer"): answered += 1
        for p in s.get("passages", []) or []:
            for q in p.get("questions", []):
                total_q += 1
                if q.get("answer"): answered += 1
    if total_q > 0:
        pct = answered * 100 // total_q
        if answered == 0:
            issues.append(f"[answers] 答案完全未填(0/{total_q})— 等 Step 2.5 从 key 抽")
        elif pct < 90:
            issues.append(f"[answers] 答案覆盖率 {pct}% ({answered}/{total_q})")

    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("type", nargs="?", choices=["cet6", "ky1"], help="类型")
    ap.add_argument("slug", nargs="?", help="目标 slug")
    ap.add_argument("--all", action="store_true", help="校验所有")
    args = ap.parse_args()

    targets = []
    if args.all:
        types = [args.type] if args.type else list(EXPECTED_BY_TYPE.keys())
        for t in types:
            d = EXAMS_BASE / t
            if not d.exists(): continue
            for f in sorted(d.glob("*.json")):
                if f.name.startswith("_"): continue
                targets.append((t, f.stem, f))
    else:
        if not args.type or not args.slug:
            ap.error("需要 type + slug,或者 --all")
        targets.append((args.type, args.slug, EXAMS_BASE / args.type / f"{args.slug}.json"))

    report = {"ok": [], "warn": [], "fail": []}
    for typ, slug, path in targets:
        if not path.exists():
            print(f"FAIL  {typ}/{slug}  文件不存在")
            report["fail"].append({"type": typ, "slug": slug, "issues": ["文件不存在"]})
            continue
        try:
            exam = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"FAIL  {typ}/{slug}  JSON 加载失败: {e}")
            report["fail"].append({"type": typ, "slug": slug, "issues": [str(e)]})
            continue

        issues = validate_exam(exam)
        # 严重:section 缺失 / 题数错 → fail;只缺答案 → warn;其他 → warn
        critical = [i for i in issues if "section 缺失" in i or "题数" in i or "选项不全" in i]
        if critical:
            print(f"FAIL  {typ}/{slug}")
            for i in issues:
                marker = "  ✗" if i in critical else "  •"
                print(f"{marker} {i}")
            report["fail"].append({"type": typ, "slug": slug, "issues": issues})
        elif issues:
            print(f"WARN  {typ}/{slug}")
            for i in issues:
                print(f"  • {i}")
            report["warn"].append({"type": typ, "slug": slug, "issues": issues})
        else:
            print(f"OK    {typ}/{slug}")
            report["ok"].append({"type": typ, "slug": slug})

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"汇总: OK={len(report['ok'])} WARN={len(report['warn'])} FAIL={len(report['fail'])}")
    print(f"报告: {REPORT_PATH}")


if __name__ == "__main__":
    main()
