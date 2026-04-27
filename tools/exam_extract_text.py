"""
Step 1 (真题流水线):把 cet_eg/ 和 KY_eg/ 下所有 PDF 抽成纯文本。

usage:
    python tools/exam_extract_text.py                # 全量抽取
    python tools/exam_extract_text.py --limit 5      # 只抽前 5 份(调试)
    python tools/exam_extract_text.py --type cet6    # 只抽某一类(cet4/cet6/ky1)
    python tools/exam_extract_text.py --skip-existing # 跳过已抽过的

输出:
    data/exams/_raw/<type>/<slug>/<role>_<filename>.txt
    data/exams/_raw/manifest.json   ← 全量清单 + 每条分类元数据
    data/exams/_raw/summary.txt     ← 人看的汇总
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [ROOT / "cet_eg", ROOT / "KY_eg"]
OUT_BASE = ROOT / "data" / "exams" / "_raw"

CN_TO_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
}

ROLE_KEYWORDS = ["解析", "答案", "详解", "细解", "详细", "解析册", "参考"]


def path_has(path_text: str, pattern: str) -> bool:
    return re.search(pattern, path_text, re.I) is not None


def find_cet_year_month(path: Path) -> tuple[int, int]:
    date_re = re.compile(r"(?<![\d-])((?:19|20)\d{2})\s*(?:年|[.\-_])\s*(1[0-2]|0?[1-9])\s*(?:月)?(?!\d)")
    texts = [path.name, *[part for part in reversed(path.parts)]]
    for text in texts:
        m = date_re.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return 0, 0


def classify(path: Path) -> dict:
    """根据文件名 + 路径推断试卷元信息。"""
    full = str(path).replace("\\", "/")
    name = path.name
    # 路径中常见"四六级"的合并提法会同时命中"四级"和"六级",分类时跳过
    full_clean = full.replace("四六级", "")

    # 1) 类型 —— 文件名优先(最具体),再退回路径
    if path_has(name, r"CET4") or "四级" in name:
        type_ = "cet4"
    elif path_has(name, r"CET6") or "六级" in name:
        type_ = "cet6"
    elif any(k in name for k in ["英语一", "英一", "考研"]):
        type_ = "ky1"
    elif path_has(full_clean, r"CET4") or "四级" in full_clean:
        type_ = "cet4"
    elif path_has(full_clean, r"CET6") or "六级" in full_clean:
        type_ = "cet6"
    elif any(k in full for k in ["KY_eg", "考研", "英语一", "英一"]):
        type_ = "ky1"
    else:
        type_ = "unknown"

    # 2) 角色:paper / key / supplementary
    # 优先级:
    #   1. "逐题细解" / "真相-解析" / 文件名含"细解"/"逐题" → key(真正的逐题分析)
    #   2. 文件名含"真题" → paper
    #   3. 文件名含 解析/答案/详解 等关键词 → key
    #   4. 专项练习 → supplementary
    #   5. fallback by path
    DEEP_ANALYSIS = ["逐题细解", "真相-解析", "解析册"]
    if any(k in full for k in DEEP_ANALYSIS) or any(k in name for k in ["逐题", "细解"]):
        role = "key"
    elif any(k in name for k in ROLE_KEYWORDS):
        role = "key"
    elif "真题" in name:
        role = "paper"
    elif any(k in name for k in ["逐词翻译", "翻译专项", "完型专项", "新题型专项", "专项"]):
        role = "supplementary"
    elif "真题" in full:
        role = "paper"
    elif any(k in full for k in ROLE_KEYWORDS):
        role = "key"
    else:
        role = "paper"

    # 3) 年份
    year = 0
    month = 0
    if type_ in ("cet4", "cet6"):
        year, month = find_cet_year_month(path)
    else:
        yr = re.search(r"(20\d{2})", name) or re.search(r"(20\d{2})", full)
        if yr:
            year = int(yr.group(1))

    # 5) 套数
    set_num = 0
    set_match = (
        re.search(r"第\s*([一二三四1234])\s*套", name)
        or re.search(r"第\s*([一二三四1234])\s*套", full)
        or re.search(r"卷\s*([一二三四])", name)
        or re.search(r"set\s*([1-4])", name, re.I)
    )
    if set_match:
        s = set_match.group(1)
        set_num = CN_TO_NUM.get(s, 0)

    return {
        "type": type_,
        "role": role,
        "year": year,
        "month": month,
        "set": set_num,
    }


def make_slug(meta: dict) -> str:
    t = meta["type"]
    if t == "ky1":
        return str(meta["year"]) if meta["year"] else "unknown"
    if t in ("cet4", "cet6"):
        parts = []
        if meta["year"]:
            parts.append(str(meta["year"]))
        if meta["month"]:
            parts.append(f"{meta['month']:02d}")
        if meta["set"]:
            parts.append(str(meta["set"]))
        return "-".join(parts) if parts else "unknown"
    return "unknown"


def safe_filename(stem: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^\w一-鿿\-\.]", "_", stem)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:max_len] or "file"


def extract_text(pdf_path: Path) -> tuple[str, int]:
    """提取文本,返回 (text, pages)。"""
    doc = fitz.open(pdf_path)
    try:
        chunks = []
        for i, page in enumerate(doc, 1):
            chunks.append(f"\n----- PAGE {i} -----\n")
            chunks.append(page.get_text())
        return "".join(chunks), doc.page_count
    finally:
        doc.close()


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 份(调试)")
    ap.add_argument("--types", default="cet6,ky1",
                    help="逗号分隔的处理类型,默认 cet6,ky1(已剔除 cet4)。可选:cet4,cet6,ky1,unknown")
    ap.add_argument("--skip-existing", action="store_true", help="跳过输出文件已存在的")
    return ap.parse_args()


def main():
    args = parse_args()

    OUT_BASE.mkdir(parents=True, exist_ok=True)

    # 收集所有 PDF
    all_pdfs = []
    for src_root in SOURCES:
        if not src_root.exists():
            print(f"[WARN] missing: {src_root}", file=sys.stderr)
            continue
        all_pdfs.extend(sorted(src_root.rglob("*.pdf")))

    print(f"找到 {len(all_pdfs)} 个 PDF")
    if args.limit:
        all_pdfs = all_pdfs[: args.limit]
        print(f"--limit {args.limit},只处理 {len(all_pdfs)} 份")

    manifest = []
    t_start = time.time()

    allowed_types = {t.strip() for t in args.types.split(",") if t.strip()}
    print(f"启用类型: {sorted(allowed_types)}")

    skipped_by_filter = 0
    for i, pdf in enumerate(all_pdfs, 1):
        meta = classify(pdf)
        if meta["type"] not in allowed_types:
            skipped_by_filter += 1
            continue

        slug = make_slug(meta)
        out_dir = OUT_BASE / meta["type"] / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"{meta['role']}_{safe_filename(pdf.stem)}.txt"
        out_path = out_dir / out_name

        rel_src = str(pdf.relative_to(ROOT)).replace("\\", "/")
        rel_out = str(out_path.relative_to(ROOT)).replace("\\", "/")

        record = {
            "src": rel_src,
            "out": rel_out,
            **meta,
            "slug": slug,
            "ok": False,
            "err": None,
            "chars": 0,
            "pages": 0,
        }

        if args.skip_existing and out_path.exists():
            record["ok"] = True
            record["err"] = "skipped (already exists)"
            record["chars"] = out_path.stat().st_size
            manifest.append(record)
            print(f"[{i}/{len(all_pdfs)}] SKIP {pdf.name}")
            continue

        try:
            text, pages = extract_text(pdf)
            out_path.write_text(text, encoding="utf-8")
            record["ok"] = True
            record["chars"] = len(text)
            record["pages"] = pages
        except Exception as e:
            record["err"] = str(e)

        manifest.append(record)
        status = "OK" if record["ok"] else "ERR"
        print(f"[{i}/{len(all_pdfs)}] {status:3s} {meta['type']:7s} {meta['role']:13s} {slug:12s} ({record['chars']:>6d} chars) {pdf.name}")

    # 写 manifest
    (OUT_BASE / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 写 summary
    summary = build_summary(manifest, time.time() - t_start, skipped_by_filter)
    (OUT_BASE / "summary.txt").write_text(summary, encoding="utf-8")
    print("\n" + summary)


def build_summary(manifest: list, elapsed: float, skipped_by_filter: int = 0) -> str:
    from collections import Counter

    lines = []
    lines.append("=" * 60)
    lines.append("PDF 抽取汇总")
    lines.append("=" * 60)
    if skipped_by_filter:
        lines.append(f"按类型过滤跳过: {skipped_by_filter}")
    lines.append(f"总文件数:  {len(manifest)}")
    ok = [r for r in manifest if r["ok"]]
    bad = [r for r in manifest if not r["ok"]]
    lines.append(f"成功:      {len(ok)}")
    lines.append(f"失败:      {len(bad)}")
    lines.append(f"耗时:      {elapsed:.1f} 秒")
    total_chars = sum(r["chars"] for r in ok)
    lines.append(f"总字符数:  {total_chars:,}")
    lines.append("")

    by_type = Counter(r["type"] for r in manifest)
    lines.append("按类型:")
    for t, c in by_type.most_common():
        lines.append(f"  {t:10s} {c}")
    lines.append("")

    by_role = Counter(r["role"] for r in manifest)
    lines.append("按角色:")
    for r_, c in by_role.most_common():
        lines.append(f"  {r_:14s} {c}")
    lines.append("")

    # 各类型 paper 覆盖
    lines.append("各类型 paper 卷数(slug 唯一计数):")
    for t in ["cet4", "cet6", "ky1"]:
        slugs = {r["slug"] for r in manifest if r["type"] == t and r["role"] == "paper"}
        lines.append(f"  {t:10s} {len(slugs):>3d} 卷  样例: {', '.join(sorted(slugs)[:5])}")
    lines.append("")

    if bad:
        lines.append("失败列表(前 10):")
        for r in bad[:10]:
            lines.append(f"  {r['src']}  →  {r['err']}")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
