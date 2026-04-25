"""
扫描 data/exams/<type>/*.json,生成 data/exams/index.json 给前端用。
按完整度分级:complete(题数 100%) / partial / paper-only。
"""

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
EXAMS_BASE = ROOT / "data" / "exams"

CET6_EXPECTED = {
    "writing": {"prompt_min_chars": 30},
    "listening": {"q": 25},
    "reading-banked": {"q": 10, "wb": 15},
    "reading-matching": {"q": 10, "para_min": 9},
    "reading-mcq": {"q": 10},
    "translation": {"source_min": 80},
}


def grade_exam(exam: dict) -> dict:
    sections_by_id = {s["id"]: s for s in exam.get("sections", [])}
    score = 0
    issues = []
    section_status = {}

    for sid, rule in CET6_EXPECTED.items():
        s = sections_by_id.get(sid)
        if not s:
            section_status[sid] = "missing"
            issues.append(f"{sid} 缺")
            continue

        ok = True
        if "q" in rule:
            qcount = sum(len(p.get("questions", [])) for p in s.get("passages", []))
            qcount += len(s.get("questions") or [])
            if qcount != rule["q"]:
                ok = False
                issues.append(f"{sid} 题数 {qcount}")
        if "wb" in rule:
            if len(s.get("wordBank") or {}) != rule["wb"]:
                ok = False
                issues.append(f"{sid} wordBank")
        if "para_min" in rule:
            if len(s.get("paragraphs") or []) < rule["para_min"]:
                ok = False
                issues.append(f"{sid} 段数")
        if "prompt_min_chars" in rule:
            if len(s.get("prompt", "") + s.get("directions", "")) < rule["prompt_min_chars"]:
                ok = False
                issues.append(f"{sid} prompt 短")
        if "source_min" in rule:
            if len(s.get("source", "")) < rule["source_min"]:
                ok = False
                issues.append(f"{sid} 中文短")

        section_status[sid] = "ok" if ok else "bad"
        if ok:
            score += 1

    full_count = len(CET6_EXPECTED)
    return {
        "score": score,
        "max": full_count,
        "completeness": score / full_count,
        "issues": issues,
        "section_status": section_status,
    }


def grade_to_label(g: dict) -> str:
    pct = g["completeness"]
    if pct >= 1.0:
        return "complete"
    if pct >= 0.7:
        return "near-complete"
    if pct >= 0.4:
        return "partial"
    return "paper-only"


def main():
    out = {"exams": []}
    for type_dir in sorted(EXAMS_BASE.iterdir()):
        if not type_dir.is_dir() or type_dir.name.startswith("_"):
            continue
        type_ = type_dir.name
        for f in sorted(type_dir.glob("*.json")):
            if f.name.startswith("_"):
                continue
            try:
                exam = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"SKIP {f.name}: {e}")
                continue
            grade = grade_exam(exam)
            label = grade_to_label(grade)
            out["exams"].append({
                "id": exam.get("id", f.stem),
                "type": type_,
                "year": exam.get("year"),
                "month": exam.get("month"),
                "set": exam.get("set"),
                "title": exam.get("title", f.stem),
                "file": f"{type_}/{f.name}",
                "completeness": round(grade["completeness"], 2),
                "label": label,
                "sectionStatus": grade["section_status"],
                "issues": grade["issues"],
            })

    out["exams"].sort(key=lambda x: (x["type"], -(x.get("year") or 0), -(x.get("month") or 0), x.get("set") or 0))
    out["summary"] = {
        "total": len(out["exams"]),
        "complete": sum(1 for e in out["exams"] if e["label"] == "complete"),
        "near": sum(1 for e in out["exams"] if e["label"] == "near-complete"),
        "partial": sum(1 for e in out["exams"] if e["label"] == "partial"),
        "paperOnly": sum(1 for e in out["exams"] if e["label"] == "paper-only"),
    }

    out_path = EXAMS_BASE / "index.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入 {out_path}")
    print(f"汇总: total={out['summary']['total']} complete={out['summary']['complete']}"
          f" near={out['summary']['near']} partial={out['summary']['partial']}"
          f" paperOnly={out['summary']['paperOnly']}")


if __name__ == "__main__":
    main()
