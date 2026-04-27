"""
tools/exam_llm_enrich.py

使用 LLM API 对真题数据进行两种操作:
  extract-answers  : 对 reading-mcq / reading-matching / banked-cloze 中
                     answer=null 的题目推断答案并写回 JSON
  validate         : 对现有答案进行验证,输出可信度和可能错误
  extract-partb    : 从 KY1 原始文本中提取 Part B 结构并写回

用法:
    python tools/exam_llm_enrich.py cet6 2023-12-1 --mode extract-answers
    python tools/exam_llm_enrich.py cet6 2023-12-1 --mode extract-answers --provider deepseek
    python tools/exam_llm_enrich.py cet6 --all --mode extract-answers --section reading-mcq
    python tools/exam_llm_enrich.py ky1 2020 --mode extract-partb
    python tools/exam_llm_enrich.py cet6 2023-12-1 --mode validate
    python tools/exam_llm_enrich.py ky1 --all --mode validate

环境变量:
    ANTHROPIC_API_KEY  使用 claude 时必填
    DEEPSEEK_API_KEY   使用 deepseek 时必填

输出:
    data/exams/{type}/{slug}.json  (就地修改,保留已有答案)
    data/exams/_llm_report.json    (汇总日志)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import anthropic
try:
    from openai import OpenAI
    _has_openai = True
except ImportError:
    _has_openai = False

# 自动读取项目根目录下的 .env / deepseek.env
def _load_env_files():
    for name in ("deepseek.env", ".env"):
        p = Path(__file__).resolve().parent.parent / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() and k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()

_load_env_files()

ROOT = Path(__file__).resolve().parent.parent
EXAMS_BASE = ROOT / "data" / "exams"
RAW_BASE = ROOT / "data" / "exams" / "_raw"
REPORT_PATH = EXAMS_BASE / "_llm_report.json"

# Claude 模型
CLAUDE_EXTRACT_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_VALIDATE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_PARTB_MODEL    = "claude-sonnet-4-6"

# DeepSeek 模型
DEEPSEEK_EXTRACT_MODEL = "deepseek-v4-flash"
DEEPSEEK_VALIDATE_MODEL = "deepseek-v4-flash"
DEEPSEEK_PARTB_MODEL   = "deepseek-reasoner"  # R1，推理更强

# 兼容旧引用
EXTRACT_MODEL = CLAUDE_EXTRACT_MODEL
VALIDATE_MODEL = CLAUDE_VALIDATE_MODEL
PARTB_MODEL = CLAUDE_PARTB_MODEL


# ──────────────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_report() -> dict:
    if REPORT_PATH.exists():
        return load_json(REPORT_PATH)
    return {"entries": []}


def call_llm(client, user_text: str,
             system: str = "", model: str = CLAUDE_EXTRACT_MODEL,
             cache_user: bool = False) -> str:
    """统一 LLM 调用，自动识别 Claude / DeepSeek 客户端。"""
    if isinstance(client, anthropic.Anthropic):
        content: list = []
        if cache_user:
            content = [{"type": "text", "text": user_text,
                        "cache_control": {"type": "ephemeral"}}]
        else:
            content = user_text
        kwargs: dict = dict(model=model, max_tokens=1024,
                            messages=[{"role": "user", "content": content}])
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return resp.content[0].text
    else:
        # OpenAI-compatible（DeepSeek）
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_text})
        resp = client.chat.completions.create(
            model=model, max_tokens=1024, messages=messages
        )
        return resp.choices[0].message.content


# 向后兼容旧调用
def call_claude(client, user_text: str, system: str = "",
                model: str = CLAUDE_EXTRACT_MODEL, cache_user: bool = False) -> str:
    return call_llm(client, user_text, system, model, cache_user)


def extract_json_from(text: str) -> dict:
    """从 LLM 响应中提取第一个 JSON 对象。"""
    text = text.strip()
    # 去掉 Markdown 代码块
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return {}


def find_raw_paper(exam_type: str, slug: str) -> Optional[Path]:
    """找原始 paper txt 文件(优先可复制版)。"""
    raw_dir = RAW_BASE / exam_type / slug
    if not raw_dir.exists():
        return None
    for pat in ["paper_*可复制*.txt", "paper_*搜索*.txt", "paper_*.txt"]:
        files = sorted(raw_dir.glob(pat))
        if files:
            return files[0]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# System Prompts
# ──────────────────────────────────────────────────────────────────────────────

SYS_EXTRACT = """\
You are an expert at Chinese English proficiency exams (CET-6 and 考研英语).
Answer exam questions by carefully reading the provided passages.
Return ONLY a valid JSON object with key "answers" mapping question numbers (as strings) to answer letters.
Example: {"answers": {"46": "B", "47": "A", "48": "C"}}
Do not output any explanation, only the JSON."""

SYS_VALIDATE = """\
You are an expert at Chinese English proficiency exams (CET-6 and 考研英语).
Verify whether the claimed answers to exam questions are correct by reading the passage.
Return ONLY a valid JSON object with:
  "correct": list of question number strings where the claimed answer is right
  "wrong":   list of {"q":"46","claimed":"B","correct":"C","note":"brief reason"}
  "uncertain": list of question number strings where you are not confident
Example: {"correct":["46","47"],"wrong":[{"q":"48","claimed":"B","correct":"C","note":"passage says X"}],"uncertain":[]}
Only output the JSON."""

SYS_PARTB = """\
You are parsing a Chinese graduate entrance exam (考研英语一) Section II Part B.

Two possible formats:
1. Paragraph-ordering: 8 paragraphs labeled [A]-[H], questions 41-45 fill missing paragraph slots
2. Name-comment matching: comments by named people (numbers 41-45), statements [A]-[G], match names to statements

Extract structure and return ONLY a JSON object:

For paragraph-ordering:
{"format":"paragraph-ordering",
 "paragraphs":[{"label":"A","text":"..."},...],
 "fixed":{"41":"A","43":"E","45":"H"},
 "questions":[{"number":41,"answer":"B"},{"number":42,"answer":"F"},{"number":43,"answer":null},{"number":44,"answer":"D"},{"number":45,"answer":null}]}

For name-comment matching:
{"format":"name-comment",
 "comments":[{"number":41,"name":"Hannah","text":"..."},...],
 "statements":[{"label":"A","text":"..."},...],
 "questions":[{"number":41,"answer":"E"},{"number":42,"answer":"C"},...]}

Set answer to null if you cannot determine it confidently.
Only output the JSON, no other text."""


# ──────────────────────────────────────────────────────────────────────────────
# Extract Answers — reading-mcq
# ──────────────────────────────────────────────────────────────────────────────

def _extract_reading_mcq(client: anthropic.Anthropic, sec: dict, dry_run: bool) -> dict:
    filled = {}
    for psg in sec.get("passages", []):
        null_qs = [q for q in psg.get("questions", []) if not q.get("answer")]
        if not null_qs:
            continue
        passage_text = psg.get("text", "").strip()
        if not passage_text:
            continue

        q_lines = []
        for q in psg.get("questions", []):
            if q.get("answer"):
                continue
            q_lines.append(f"\n{q['number']}. {q.get('stem', '')}")
            for letter in "ABCD":
                opt = q.get("options", {}).get(letter, "")
                if opt:
                    q_lines.append(f"  {letter}) {opt}")

        prompt = (
            f"PASSAGE:\n{passage_text}\n\n"
            f"QUESTIONS (answer each with the correct letter A/B/C/D):\n"
            + "".join(q_lines)
            + '\n\nReturn JSON: {"answers": {"46": "A", ...}}'
        )

        if dry_run:
            print(f"    [dry-run] reading-mcq: {len(null_qs)} questions in {psg.get('label', '?')}")
            continue

        resp = call_claude(client, prompt, SYS_EXTRACT)
        data = extract_json_from(resp)
        for q in psg["questions"]:
            num = str(q["number"])
            if not q.get("answer") and num in data.get("answers", {}):
                ans = data["answers"][num].strip().upper()
                if ans in "ABCD":
                    q["answer"] = ans
                    q.setdefault("answerMeta", {}).update({"sourceType": "llm-extract", "model": EXTRACT_MODEL})
                    filled[num] = ans
    return filled


# ──────────────────────────────────────────────────────────────────────────────
# Extract Answers — reading-matching
# ──────────────────────────────────────────────────────────────────────────────

def _extract_matching(client: anthropic.Anthropic, sec: dict, dry_run: bool) -> dict:
    null_qs = [q for q in sec.get("questions", []) if not q.get("answer")]
    if not null_qs:
        return {}
    paragraphs = sec.get("paragraphs", [])
    if not paragraphs:
        return {}

    para_str = "\n\n".join(f"{p['label']}) {p['text']}" for p in paragraphs)
    q_str = "\n".join(f"{q['number']}. {q.get('stem', '')}" for q in null_qs)

    prompt = (
        f"PASSAGE PARAGRAPHS (labeled A-N):\n{para_str}\n\n"
        f"MATCHING QUESTIONS (find which paragraph best contains each piece of information):\n{q_str}\n\n"
        "A paragraph letter can be used more than once.\n"
        'Return JSON: {"answers": {"36": "C", "37": "H", ...}}'
    )

    if dry_run:
        print(f"    [dry-run] matching: {len(null_qs)} questions")
        return {}

    resp = call_claude(client, prompt, SYS_EXTRACT)
    data = extract_json_from(resp)
    filled = {}
    valid_labels = {p["label"].upper() for p in paragraphs}
    for q in sec["questions"]:
        num = str(q["number"])
        if not q.get("answer") and num in data.get("answers", {}):
            ans = data["answers"][num].strip().upper()
            if ans in valid_labels:
                q["answer"] = ans
                q.setdefault("answerMeta", {}).update({"sourceType": "llm-extract", "model": EXTRACT_MODEL})
                filled[num] = ans
    return filled


# ──────────────────────────────────────────────────────────────────────────────
# Extract Answers — banked-cloze (从原始文本读取带编号空白的段落)
# ──────────────────────────────────────────────────────────────────────────────

def _load_banked_raw(exam_type: str, slug: str) -> Optional[str]:
    """从原始 paper 文本中提取 banked-cloze 段落(含编号空格)。"""
    paper_path = find_raw_paper(exam_type, slug)
    if not paper_path:
        return None
    raw = paper_path.read_text(encoding="utf-8", errors="replace")
    # 找 Section A (banked-cloze) 块
    # 从第二个 "Section A" 往后(第一个在 Listening)
    m_all = list(re.finditer(r"^\s*Section\s+A\s*$", raw, re.M))
    if len(m_all) < 2:
        m_all = list(re.finditer(r"In this section.*?ten blanks", raw, re.S | re.I))
        if not m_all:
            return None
        start = m_all[0].start()
    else:
        start = m_all[1].start()
    # 找结束(Section B)
    end_m = re.search(r"^\s*Section\s+B\s*$", raw[start:], re.M)
    end = start + end_m.start() if end_m else start + 4000
    return raw[start:end].strip()


def _extract_banked_cloze(client: anthropic.Anthropic, sec: dict,
                           exam_type: str, slug: str, dry_run: bool) -> dict:
    null_qs = [q for q in sec.get("questions", []) if not q.get("answer")]
    if not null_qs:
        return {}

    raw_block = _load_banked_raw(exam_type, slug)
    word_bank = sec.get("wordBank", {})

    if not raw_block:
        # 降级:用解析后的 passage(空格未编号)
        raw_block = sec.get("passage", "")
    if not raw_block:
        return {}

    bank_str = "  ".join(f"{k}) {v}" for k, v in sorted(word_bank.items()))
    q_nums = [str(q["number"]) for q in null_qs]

    prompt = (
        f"CLOZE PASSAGE (blanks numbered {q_nums[0]}-{q_nums[-1]}):\n{raw_block}\n\n"
        f"WORD BANK:\n{bank_str}\n\n"
        f"Fill blanks {', '.join(q_nums)} with the best word letter from the bank.\n"
        'Return JSON: {"answers": {"26": "F", "27": "A", ...}}'
    )

    if dry_run:
        print(f"    [dry-run] banked-cloze: {len(null_qs)} blanks")
        return {}

    resp = call_claude(client, prompt, SYS_EXTRACT)
    data = extract_json_from(resp)
    filled = {}
    valid_keys = set(word_bank.keys())
    for q in sec["questions"]:
        num = str(q["number"])
        if not q.get("answer") and num in data.get("answers", {}):
            ans = data["answers"][num].strip().upper()
            if ans in valid_keys:
                q["answer"] = ans
                q.setdefault("answerMeta", {}).update({"sourceType": "llm-extract", "model": EXTRACT_MODEL})
                filled[num] = ans
    return filled


# ──────────────────────────────────────────────────────────────────────────────
# Validate Answers
# ──────────────────────────────────────────────────────────────────────────────

def _validate_section(client: anthropic.Anthropic, sec: dict, dry_run: bool) -> dict:
    results: dict = {"correct": [], "wrong": [], "uncertain": []}
    sec_type = sec.get("type", "")

    if sec_type == "reading-mcq":
        for psg in sec.get("passages", []):
            answered = [q for q in psg.get("questions", []) if q.get("answer") and q.get("stem")]
            if not answered:
                continue
            q_lines = []
            for q in answered:
                q_lines.append(f"\n{q['number']}. {q.get('stem','')} [claimed: {q['answer']}]")
                for l in "ABCD":
                    opt = q.get("options", {}).get(l, "")
                    if opt:
                        q_lines.append(f"  {l}) {opt}")
            passage = psg.get("text", "")
            if not passage:
                continue
            prompt = (
                f"PASSAGE:\n{passage}\n\n"
                "QUESTIONS WITH CLAIMED ANSWERS:\n"
                + "".join(q_lines)
            )
            if dry_run:
                print(f"    [dry-run] validate reading-mcq: {len(answered)} questions")
                continue
            resp = call_claude(client, prompt, SYS_VALIDATE, model=VALIDATE_MODEL)
            d = extract_json_from(resp)
            for k in ("correct", "wrong", "uncertain"):
                results[k].extend(d.get(k, []))

    elif sec_type == "matching":
        answered = [q for q in sec.get("questions", []) if q.get("answer")]
        if not answered:
            return results
        paras = sec.get("paragraphs", [])
        if not paras:
            return results
        para_str = "\n\n".join(f"{p['label']}) {p['text']}" for p in paras)
        q_lines = [f"{q['number']}. {q.get('stem','')} [claimed: {q['answer']}]" for q in answered]
        prompt = (
            f"PARAGRAPHS:\n{para_str}\n\n"
            "MATCHING QUESTIONS WITH CLAIMED ANSWERS:\n"
            + "\n".join(q_lines)
        )
        if dry_run:
            print(f"    [dry-run] validate matching: {len(answered)} questions")
            return results
        resp = call_claude(client, prompt, SYS_VALIDATE, model=VALIDATE_MODEL)
        d = extract_json_from(resp)
        for k in ("correct", "wrong", "uncertain"):
            results[k].extend(d.get(k, []))

    elif sec_type == "banked-cloze":
        answered = [q for q in sec.get("questions", []) if q.get("answer")]
        if not answered:
            return results
        passage = sec.get("passage", "")
        word_bank = sec.get("wordBank", {})
        bank_str = "  ".join(f"{k}) {v}" for k, v in sorted(word_bank.items()))
        q_lines = [f"Blank {q['number']} [claimed: {q['answer']}]" for q in answered]
        prompt = (
            f"CLOZE PASSAGE:\n{passage}\n\n"
            f"WORD BANK: {bank_str}\n\n"
            "CLAIMED ANSWERS (blank number → word letter):\n"
            + "\n".join(q_lines)
        )
        if dry_run:
            print(f"    [dry-run] validate banked-cloze: {len(answered)} blanks")
            return results
        resp = call_claude(client, prompt, SYS_VALIDATE, model=VALIDATE_MODEL)
        d = extract_json_from(resp)
        for k in ("correct", "wrong", "uncertain"):
            results[k].extend(d.get(k, []))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# KY1 Part B Extraction
# ──────────────────────────────────────────────────────────────────────────────

def extract_ky1_partb(client: anthropic.Anthropic, slug: str, dry_run: bool) -> Optional[dict]:
    paper_path = find_raw_paper("ky1", slug)
    if not paper_path:
        print(f"  No raw paper found for ky1/{slug}")
        return None

    raw = paper_path.read_text(encoding="utf-8", errors="replace")
    # 找 Part B 块
    pb_m = re.search(r"^\s*Part\s+B\s*$", raw, re.M)
    if not pb_m:
        print(f"  No 'Part B' marker in {paper_path.name}")
        return None
    pc_m = re.search(r"^\s*Part\s+C\s*$", raw[pb_m.start():], re.M)
    end = pb_m.start() + pc_m.start() if pc_m else pb_m.start() + 5000
    part_b_text = raw[pb_m.start():end].strip()

    if dry_run:
        print(f"  [dry-run] Would extract Part B ({len(part_b_text)} chars) from {paper_path.name}")
        return None

    resp = call_claude(
        client,
        f"Extract the structure of this exam section:\n\n{part_b_text}",
        SYS_PARTB,
        model=PARTB_MODEL,
    )
    return extract_json_from(resp)


def apply_ky1_partb(exam_json: dict, partb_data: dict, slug: str) -> bool:
    if not partb_data:
        return False

    fmt = partb_data.get("format", "")

    for sec in exam_json.get("sections", []):
        if sec.get("id") != "new-question":
            continue

        if fmt == "paragraph-ordering":
            paras = partb_data.get("paragraphs", [])
            qs_raw = partb_data.get("questions", [])
            fixed = partb_data.get("fixed", {})
            if paras:
                sec["paragraphs"] = paras
            if qs_raw:
                existing_ans = {str(q.get("number")): q.get("answer")
                                for q in sec.get("questions", []) if q.get("answer")}
                new_qs = []
                for qr in qs_raw:
                    num = qr["number"]
                    ans = existing_ans.get(str(num)) or qr.get("answer")
                    new_qs.append({
                        "id": f"q{num}", "number": num,
                        "stem": f"Box {num}",
                        "answer": ans,
                        "answerMeta": {"sourceType": "llm-extract", "model": PARTB_MODEL},
                        "explanation": "",
                    })
                sec["questions"] = new_qs
            return True

        elif fmt == "name-comment":
            comments = partb_data.get("comments", [])
            statements = partb_data.get("statements", [])
            qs_raw = partb_data.get("questions", [])
            if comments:
                sec["paragraphs"] = [
                    {"label": str(c["number"]), "text": f"{c['name']}\n{c['text']}"}
                    for c in comments
                ]
            if statements:
                sec["options"] = {s["label"]: s["text"] for s in statements}
            if qs_raw:
                existing_ans = {str(q.get("number")): q.get("answer")
                                for q in sec.get("questions", []) if q.get("answer")}
                name_map = {c["number"]: c["name"] for c in comments}
                new_qs = []
                for qr in qs_raw:
                    num = qr["number"]
                    ans = existing_ans.get(str(num)) or qr.get("answer")
                    new_qs.append({
                        "id": f"q{num}", "number": num,
                        "stem": name_map.get(num, str(num)),
                        "answer": ans,
                        "answerMeta": {"sourceType": "llm-extract", "model": PARTB_MODEL},
                        "explanation": "",
                    })
                sec["questions"] = new_qs
            return True

    return False


# ──────────────────────────────────────────────────────────────────────────────
# Main processing per file
# ──────────────────────────────────────────────────────────────────────────────

TARGET_TYPES = {"reading-mcq", "matching", "banked-cloze"}


def process_file(
    client,
    exam_type: str,
    slug: str,
    mode: str,
    target_sections: set,
    dry_run: bool,
) -> dict:
    path = EXAMS_BASE / exam_type / f"{slug}.json"
    if not path.exists():
        return {"slug": slug, "status": "not-found"}

    exam = load_json(path)
    report: dict = {"slug": slug, "type": exam_type, "mode": mode, "sections": {}}
    changed = False

    # ── extract-partb (KY1 only) ──────────────────────────────────────────────
    if mode == "extract-partb":
        if exam_type != "ky1":
            return {"slug": slug, "status": "skip-not-ky1"}
        partb_data = extract_ky1_partb(client, slug, dry_run)
        if partb_data:
            ok = apply_ky1_partb(exam, partb_data, slug)
            if ok and not dry_run:
                write_json(path, exam)
                changed = True
            report["sections"]["new-question"] = {
                "format": partb_data.get("format"),
                "changed": ok,
            }
        return report

    # ── extract-answers / validate ────────────────────────────────────────────
    for sec in exam.get("sections", []):
        sec_type = sec.get("type", "")
        if sec_type not in target_sections:
            continue

        sec_id = sec.get("id", sec_type)

        if mode == "extract-answers":
            if sec_type == "reading-mcq":
                filled = _extract_reading_mcq(client, sec, dry_run)
            elif sec_type == "matching":
                filled = _extract_matching(client, sec, dry_run)
            elif sec_type == "banked-cloze":
                filled = _extract_banked_cloze(client, sec, exam_type, slug, dry_run)
            else:
                filled = {}
            if filled:
                changed = True
            report["sections"][sec_id] = {"filled": len(filled), "answers": filled}

        elif mode == "validate":
            results = _validate_section(client, sec, dry_run)
            report["sections"][sec_id] = results

        time.sleep(0.3)   # 限速

    if changed and not dry_run:
        write_json(path, exam)

    return report


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="LLM-powered exam enrichment")
    ap.add_argument("type", choices=["cet6", "ky1"], help="exam type")
    ap.add_argument("slug", nargs="?", help="year slug (omit with --all)")
    ap.add_argument("--mode", choices=["extract-answers", "validate", "extract-partb"],
                    default="extract-answers")
    ap.add_argument("--section", default="all",
                    help="reading-mcq / matching / banked-cloze / all")
    ap.add_argument("--all", action="store_true", dest="all_files")
    ap.add_argument("--dry-run", action="store_true", help="print plan without calling API")
    ap.add_argument("--provider", choices=["claude", "deepseek"], default="claude",
                    help="使用哪个 LLM 提供商 (默认 claude)")
    args = ap.parse_args()

    if args.provider == "deepseek":
        if not _has_openai:
            print("ERROR: 需要先安装 openai 包: pip install openai", file=sys.stderr)
            sys.exit(1)
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            print("ERROR: DEEPSEEK_API_KEY not set", file=sys.stderr)
            sys.exit(1)
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        # 覆盖模型常量让后续函数直接用
        global EXTRACT_MODEL, VALIDATE_MODEL, PARTB_MODEL
        EXTRACT_MODEL  = DEEPSEEK_EXTRACT_MODEL
        VALIDATE_MODEL = DEEPSEEK_VALIDATE_MODEL
        PARTB_MODEL    = DEEPSEEK_PARTB_MODEL
        print(f"Provider: DeepSeek  extract={EXTRACT_MODEL}  partb={PARTB_MODEL}")
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
            sys.exit(1)
        client = anthropic.Anthropic(api_key=api_key)
        print(f"Provider: Claude  extract={CLAUDE_EXTRACT_MODEL}  partb={CLAUDE_PARTB_MODEL}")

    if args.section == "all":
        target_sections = TARGET_TYPES
    else:
        target_sections = {args.section}

    if args.all_files or not args.slug:
        slugs = [p.stem for p in sorted((EXAMS_BASE / args.type).glob("*.json"))]
    else:
        slugs = [args.slug]

    all_reports = []
    for slug in slugs:
        print(f"[{args.type}/{slug}] mode={args.mode}")
        try:
            r = process_file(client, args.type, slug, args.mode, target_sections, args.dry_run)
            all_reports.append(r)
            for sid, sr in r.get("sections", {}).items():
                filled = sr.get("filled", 0)
                wrong = len(sr.get("wrong", []))
                uncertain = len(sr.get("uncertain", []))
                if filled:
                    print(f"  {sid}: filled {filled} answers")
                if wrong:
                    print(f"  {sid}: {wrong} possibly wrong → {sr['wrong']}")
                if uncertain:
                    print(f"  {sid}: {uncertain} uncertain")
        except anthropic.APIError as e:
            print(f"  API error: {e}")
            all_reports.append({"slug": slug, "type": args.type, "error": str(e)})
        except Exception as e:
            print(f"  ERROR: {e}")
            all_reports.append({"slug": slug, "type": args.type, "error": str(e)})

    if not args.dry_run:
        report = load_report()
        report.setdefault("entries", []).extend(all_reports)
        write_json(REPORT_PATH, report)
        print(f"\nReport appended → {REPORT_PATH}")

    print("Done.")


if __name__ == "__main__":
    main()
