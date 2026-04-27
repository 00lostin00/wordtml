"""
对图片版 PDF key 文件做 OCR (Step 2 之外的修复管线)。

针对 _failure_report.md 里类别 2 的 9 卷:
  2018-12-{1,2,3} / 2019-12-{1,2,3} / 2024-12-{1,2,3}
这些 key PDF 是扫描图,PyMuPDF 抽不出文字,需要 OCR。

usage:
    python tools/exam_ocr_keys.py --auto         # 自动找类别 2 的 9 卷
    python tools/exam_ocr_keys.py 2018-12-1      # 手动指定 slug
    python tools/exam_ocr_keys.py --auto --skip-existing   # 已 OCR 过的跳过

流程:
  1. 从 manifest.json 找 slug 对应的 key PDF 源
  2. PDF → PNG (高 DPI 渲染)
  3. PowerShell 调 windows_ocr.ps1 (Windows OCR API)
  4. 合并各页 JSON 的 text 字段 → 写入 _raw/cet6/<slug>/key_OCR.txt
  5. 提示重跑 exam_extract_answers
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import fitz  # PyMuPDF

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
RAW_BASE = ROOT / "data" / "exams" / "_raw" / "cet6"
TMP_BASE = ROOT / "tmp_exam_ocr"
OCR_SCRIPT = ROOT / "tools" / "windows_ocr.ps1"
MANIFEST = ROOT / "data" / "exams" / "_raw" / "manifest.json"

DPI_SCALE = 2.5  # 渲染倍率,影响清晰度

# 类别 2 默认目标
DEFAULT_SLUGS = [
    "2018-12-1", "2018-12-2", "2018-12-3",
    "2019-12-1", "2019-12-2", "2019-12-3",
    "2024-12-1", "2024-12-2", "2024-12-3",
]


def safe_name(text: str, max_len: int = 48) -> str:
    text = re.sub(r"[^\w一-鿿\-\.]+", "_", text)
    return text.strip("_")[:max_len] or "pdf"


SET_TOKEN_RE = {
    1: re.compile(r"(?:第\s*(?:1|一)\s*套|卷\s*(?:一|1)|第\s*(?:一|1)\s*卷)"),
    2: re.compile(r"(?:第\s*(?:2|二)\s*套|卷\s*(?:二|2)|第\s*(?:二|2)\s*卷)"),
    3: re.compile(r"(?:第\s*(?:3|三)\s*套|卷\s*(?:三|3)|第\s*(?:三|3)\s*卷)"),
}


def slug_year_month_set(slug: str) -> tuple[int | None, int | None, int | None]:
    parts = slug.split("-")
    if len(parts) < 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        return None, None, None
    set_no = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else None
    return int(parts[0]), int(parts[1]), set_no


def path_matches_year_month(path_text: str, slug: str) -> bool:
    year, month, _set_no = slug_year_month_set(slug)
    if year is None or month is None:
        return True
    # Match year and month as one adjacent date expression, but do not let
    # collection ranges such as "2015-2024年12月" satisfy slug 2024-12.
    date_re = re.compile(
        rf"(?<![\d-]){year}\s*(?:年|[.\-_])\s*0?{month}\s*(?:月)?(?!\d)"
    )
    return bool(date_re.search(path_text))


def is_cet6_source(path_text: str) -> bool:
    if re.search(r"CET4|四级", path_text, re.I):
        return False
    return bool(re.search(r"CET6|六级", path_text, re.I))


def path_set_score(path_text: str, slug: str) -> int:
    _year, _month, set_no = slug_year_month_set(slug)
    if not set_no:
        return 0
    if SET_TOKEN_RE[set_no].search(path_text):
        return 3
    if any(regex.search(path_text) for no, regex in SET_TOKEN_RE.items() if no != set_no):
        return -10
    if re.search(r"全\s*[3三]\s*套|三\s*套\s*全", path_text):
        return 1
    return 0


def source_score(path: Path, slug: str) -> tuple[int, int, int, int]:
    text = str(path)
    name = path.name
    if not is_cet6_source(text):
        return (-120, 0, 0, 0)
    if not path_matches_year_month(text, slug):
        return (-100, 0, 0, 0)
    set_score = path_set_score(text, slug)
    if set_score < 0:
        return (-90, set_score, 0, 0)
    return (
        set_score,
        1 if "解析" in name else 0,
        1 if any(k in name for k in ["答案", "详解", "细解"]) else 0,
        -len(text),
    )


def find_source_pdf(slug: str) -> Path | None:
    """从 manifest 找 slug 对应的 key PDF 源(挑最大的那份)。"""
    if not MANIFEST.exists():
        return None
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    slugs = [slug]
    # 具体套卷(2016-12-1)经常只有合并解析 PDF(2016-12),回退到年月目录。
    parts = slug.split("-")
    if len(parts) == 3 and parts[2].isdigit():
        slugs.append("-".join(parts[:2]))
    candidates = [
        r for r in manifest
        if r.get("type") == "cet6" and r.get("slug") in slugs and r.get("role") == "key"
    ]
    scored = []
    for r in candidates:
        # 拿原始 src 路径(优先选 src 路径不含临时目录的)
        src = r["src"]
        pdf_path = ROOT / src
        if pdf_path.exists():
            score = source_score(pdf_path, slug)
            if score[0] > -50:
                scored.append((score, r.get("chars", 0), pdf_path))
    if scored:
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][2]
    return find_source_pdf_by_scan(slug)


def find_source_pdf_by_scan(slug: str) -> Path | None:
    """manifest 没覆盖时,直接扫 cet_eg 找对应年月的解析 PDF。"""
    parts = slug.split("-")
    if len(parts) < 2:
        return None
    year, month = parts[0], parts[1].lstrip("0")
    month2 = f"{int(month):02d}"
    exact_re = re.compile(
        rf"{year}\s*(?:年|[\.\-_])\s*{month2 if month2 != month else f'0?{month}'}\s*(?:月)?"
    )
    candidates = []
    src_root = ROOT / "cet_eg"
    if not src_root.exists():
        return None
    for pdf in src_root.rglob("*.pdf"):
        full = str(pdf)
        name = pdf.name
        if not path_matches_year_month(full, slug):
            continue
        if not is_cet6_source(full):
            continue
        if not any(k in name for k in ["解析", "答案", "详解", "细解"]):
            continue
        if source_score(pdf, slug)[0] < -50:
            continue
        candidates.append(pdf)
    if not candidates:
        return None
    candidates.sort(key=lambda p: source_score(p, slug), reverse=True)
    return candidates[0]


def render_pdf_to_pngs(pdf_path: Path, out_dir: Path) -> int:
    """PDF 渲染为 PNG,返回页数。已存在则跳过。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    n_pages = doc.page_count
    matrix = fitz.Matrix(DPI_SCALE, DPI_SCALE)
    for i in range(n_pages):
        png_path = out_dir / f"page_{i+1:03d}.png"
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pix.save(str(png_path))
    doc.close()
    return n_pages


def run_windows_ocr(input_dir: Path, output_dir: Path) -> None:
    """调 PowerShell 跑 windows_ocr.ps1。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(OCR_SCRIPT),
        "-InputDir", str(input_dir),
        "-OutputDir", str(output_dir),
    ]
    print(f"  运行 OCR: {input_dir} -> {output_dir}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        print(f"  ⚠️ OCR stderr: {result.stderr[:500]}")
    # 简略 stdout
    if result.stdout:
        for line in result.stdout.split("\n")[:5]:
            if line.strip():
                print(f"    {line.strip()}")


def stitch_ocr_to_text(ocr_dir: Path) -> str:
    """把各页的 JSON.text 拼成一个 txt。"""
    parts = []
    for json_path in sorted(ocr_dir.glob("page_*.json")):
        # PowerShell ConvertTo-Json + Set-Content -Encoding utf8 会带 BOM
        try:
            data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            print(f"  !! JSON 解析失败 {json_path.name}: {e}")
            continue
        page_no = json_path.stem.replace("page_", "").lstrip("0") or "0"
        parts.append(f"\n----- PAGE {page_no} -----\n")
        parts.append(data.get("text", ""))
    return "\n".join(parts).strip()


def process_slug(slug: str, skip_existing: bool = False) -> dict:
    out_path = RAW_BASE / slug / f"key_OCR_{slug}.txt"
    if skip_existing and out_path.exists() and out_path.stat().st_size > 1000:
        return {"slug": slug, "status": "skip", "reason": "已存在 OCR 输出"}

    pdf_path = find_source_pdf(slug)
    if not pdf_path:
        return {"slug": slug, "status": "fail", "reason": "找不到源 key PDF"}

    pdf_key = safe_name(pdf_path.stem)
    pages_dir = TMP_BASE / slug / pdf_key / "pages"
    ocr_dir = TMP_BASE / slug / pdf_key / "ocr"

    print(f"[{slug}] 源 PDF: {pdf_path.name}")
    n_pages = render_pdf_to_pngs(pdf_path, pages_dir)
    print(f"  渲染完成: {n_pages} 页 -> {pages_dir}")

    run_windows_ocr(pages_dir, ocr_dir)

    text = stitch_ocr_to_text(ocr_dir)
    if not text:
        return {"slug": slug, "status": "fail", "reason": "OCR 输出为空"}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"  写入: {out_path} ({len(text)} 字)")
    return {"slug": slug, "status": "ok", "chars": len(text), "pages": n_pages, "out": str(out_path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*", help="要 OCR 的 slug,如 2024-12-1")
    ap.add_argument("--auto", action="store_true", help="自动选类别 2 的 9 卷")
    ap.add_argument("--skip-existing", action="store_true", help="已有 OCR 输出的跳过")
    args = ap.parse_args()

    if args.auto and not args.slugs:
        slugs = DEFAULT_SLUGS
    elif args.slugs:
        slugs = args.slugs
    else:
        ap.error("需要 slug 列表 或 --auto")

    if not OCR_SCRIPT.exists():
        print(f"ERR: 找不到 OCR 脚本 {OCR_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    results = []
    for slug in slugs:
        try:
            r = process_slug(slug, skip_existing=args.skip_existing)
        except Exception as e:
            r = {"slug": slug, "status": "fail", "reason": str(e)}
        results.append(r)
        print(f"  -> {r['status']}: {r.get('reason') or r.get('out')}")
        print()

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"汇总: OK={ok} / 总 {len(results)}")
    print()
    print("下一步:")
    print("  python tools/exam_extract_answers.py cet6 --all --write")
    print("  python tools/exam_build_index.py")


if __name__ == "__main__":
    main()
