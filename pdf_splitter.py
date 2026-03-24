#!/usr/bin/env python3
"""
PDF 书籍章节拆分工具（PDF 版）
将 PDF 文件按一级章节拆分为多个 PDF 文件，每个章节一个文件，
内容与原书籍完全一致（直接复制原始 PDF 页面，不重新渲染）。

依赖安装：
    pip install pdfplumber pypdf
"""

import re
import sys
import argparse
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("缺少依赖库，请先安装：pip install pdfplumber")
    sys.exit(1)

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("缺少依赖库，请先安装：pip install pypdf")
    sys.exit(1)


# ── 一级标题匹配模式（章/Part/Chapter 级别）──────────────────────────────────
H1_PATTERNS = [
    # 中文：第一章、第1章、第一篇、第一部 等（不含"节"）
    r'^第\s*[零一二三四五六七八九十百千\d]+\s*[章篇部]\s*.{0,30}$',
    # 英文：Chapter 1、Chapter One 等
    r'^Chapter\s+[\dIVXivx]+[\s\.:：].{0,50}$',
    # Part 分部
    r'^Part\s+[\dIVXivx]+[\s\.:：].{0,50}$',
    # 纯顶级数字编号：1. 标题（不含小数点，即非 1.1 这类）
    r'^\d+\.\s+.{2,50}$',
]

# ── 二级标题匹配模式（节/Section 级别）───────────────────────────────────────
H2_PATTERNS = [
    # 中文：第一节、第1节 等
    r'^第\s*[零一二三四五六七八九十百千\d]+\s*节\s*.{0,30}$',
    # 英文：Section 1、Section 1.1 等
    r'^Section\s+[\d\.]+[\s\.:：].{0,50}$',
    # 两级及以上数字编号：1.1 标题、1.1.1 标题
    r'^\d+\.\d+[\.\d]*\s+.{2,50}$',
]

COMPILED_H1_PATTERNS = [re.compile(p) for p in H1_PATTERNS]
COMPILED_H2_PATTERNS = [re.compile(p) for p in H2_PATTERNS]


def detect_heading_level(
    text: str,
    font_sizes: list[float],
    page_avg_font_size: float,
    doc_heading_sizes: list[float],
) -> int:
    """
    判断文本的标题层级。

    返回值：
        0 — 普通正文
        1 — 一级标题（章/Chapter/Part）
        2 — 二级标题（节/Section）

    判断策略：
    1. 先用正则规则匹配，命中 H1 模式返回 1，命中 H2 模式返回 2。
    2. 若正则未命中，则依据字体大小推断：
       - 字号 >= 文档最大标题字号 * 0.95 且文字较短 → 一级标题
       - 字号 >= 页面平均字号 * 1.3 且文字较短 → 二级标题
    """
    stripped = text.strip()
    if not stripped or len(stripped) > 100:
        return 0

    for pattern in COMPILED_H1_PATTERNS:
        if pattern.match(stripped):
            return 1

    for pattern in COMPILED_H2_PATTERNS:
        if pattern.match(stripped):
            return 2

    # 字体大小推断
    if font_sizes and page_avg_font_size > 0:
        avg_line_size = sum(font_sizes) / len(font_sizes)
        max_heading_size = max(doc_heading_sizes) if doc_heading_sizes else 0

        if max_heading_size > 0 and avg_line_size >= max_heading_size * 0.95 and len(stripped) <= 60:
            return 1
        if avg_line_size >= page_avg_font_size * 1.3 and len(stripped) <= 60:
            return 2

    return 0


def extract_page_blocks(pdf_path: str) -> list[dict]:
    """
    使用 pdfplumber 提取每页的文字块及字体信息，用于标题识别。

    返回结构：
        [
            {
                "page_num": int,          # 1-based 页码
                "page_index": int,        # 0-based 页索引（供 pypdf 使用）
                "blocks": [
                    {
                        "text": str,
                        "font_sizes": [float],
                        "page_avg_font_size": float,
                    }
                ],
            }
        ]
    """
    pages_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            words = page.extract_words(extra_attrs=["size"])
            if not words:
                pages_data.append({
                    "page_num": page_index + 1,
                    "page_index": page_index,
                    "blocks": [],
                })
                continue

            # 计算页面平均字号
            all_sizes = [word.get("size", 0) for word in words if word.get("size")]
            page_avg_font_size = sum(all_sizes) / len(all_sizes) if all_sizes else 0

            # 将相邻的词按行分组（y 坐标相近视为同一行，阈值 5 兼容更多 PDF）
            lines: list[list[dict]] = []
            current_line: list[dict] = []
            last_y: float | None = None

            for word in words:
                word_y = round(word.get("top", 0), 1)
                if last_y is None or abs(word_y - last_y) < 5:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = [word]
                last_y = word_y

            if current_line:
                lines.append(current_line)

            # 将行转换为文字块
            blocks = []
            for line_words in lines:
                line_text = " ".join(word["text"] for word in line_words)
                line_sizes = [word.get("size", 0) for word in line_words if word.get("size")]
                blocks.append({
                    "text": line_text,
                    "font_sizes": line_sizes,
                    "page_avg_font_size": page_avg_font_size,
                })

            pages_data.append({
                "page_num": page_index + 1,
                "page_index": page_index,
                "blocks": blocks,
            })

    return pages_data


def collect_doc_heading_sizes(pages_data: list[dict]) -> list[float]:
    """
    预扫描全文，收集所有疑似标题行的字号，
    用于后续字体大小推断一级标题时的参照基准。
    """
    heading_sizes: list[float] = []
    for page_info in pages_data:
        for block in page_info["blocks"]:
            font_sizes = block["font_sizes"]
            page_avg = block["page_avg_font_size"]
            if font_sizes and page_avg > 0:
                avg_line_size = sum(font_sizes) / len(font_sizes)
                if avg_line_size > page_avg * 1.2 and len(block["text"].strip()) <= 80:
                    heading_sizes.append(avg_line_size)
    return heading_sizes


def detect_h1_page_ranges(pages_data: list[dict], total_pages: int) -> list[dict]:
    """
    扫描所有页面，找出每个一级章节的起始页（0-based page_index）和标题文本。

    返回：
        [
            {
                "title": str,
                "start_page_index": int,   # 0-based，包含
                "end_page_index": int,     # 0-based，包含
            }
        ]
    """
    doc_heading_sizes = collect_doc_heading_sizes(pages_data)

    # 收集所有一级标题出现的位置
    h1_hits: list[dict] = []  # [{"title": str, "page_index": int}]

    for page_info in pages_data:
        page_index = page_info["page_index"]
        for block in page_info["blocks"]:
            text = block["text"].strip()
            if not text:
                continue

            level = detect_heading_level(
                text,
                block["font_sizes"],
                block["page_avg_font_size"],
                doc_heading_sizes,
            )

            if level == 1:
                # 同一页可能出现多个一级标题（如目录页），只取每页第一次出现
                if not h1_hits or h1_hits[-1]["page_index"] != page_index:
                    h1_hits.append({"title": text, "page_index": page_index})
                break  # 每页只取第一个一级标题，避免目录页干扰

    if not h1_hits:
        return []

    # 将相邻一级标题之间的页面范围组合成章节
    sections: list[dict] = []
    for i, hit in enumerate(h1_hits):
        start_index = hit["page_index"]
        if i + 1 < len(h1_hits):
            end_index = h1_hits[i + 1]["page_index"] - 1
        else:
            end_index = total_pages - 1

        sections.append({
            "title": hit["title"],
            "start_page_index": start_index,
            "end_page_index": end_index,
        })

    return sections


def sanitize_filename(title: str) -> str:
    """将章节标题转换为合法的文件名。"""
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', title)
    sanitized = sanitized.strip().strip('.')
    return sanitized[:80] if sanitized else "untitled"


def write_section_pdf(
    reader: PdfReader,
    start_page_index: int,
    end_page_index: int,
    output_path: Path,
) -> None:
    """
    从 PdfReader 中提取指定页范围（含首尾），写出到 output_path。
    直接复制原始 PDF 页面对象，保持内容与原书完全一致。
    """
    writer = PdfWriter()
    for page_index in range(start_page_index, end_page_index + 1):
        writer.add_page(reader.pages[page_index])

    with open(output_path, "wb") as output_file:
        writer.write(output_file)


def split_pdf_by_chapters(pdf_path: str, output_dir: str) -> None:
    """
    主函数：读取 PDF，识别一级章节边界，按章节拆分为多个 PDF 文件。
    每个输出 PDF 的内容与原书对应页面完全一致。
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"错误：文件不存在 -> {pdf_path}")
        sys.exit(1)

    if pdf_file.suffix.lower() != ".pdf":
        print(f"错误：文件不是 PDF 格式 -> {pdf_path}")
        sys.exit(1)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"正在读取 PDF：{pdf_file.name}")
    pages_data = extract_page_blocks(pdf_path)
    total_pages = len(pages_data)
    print(f"共读取 {total_pages} 页")

    print("正在识别一级章节边界...")
    sections = detect_h1_page_ranges(pages_data, total_pages)
    print(f"共识别出 {len(sections)} 个一级章节")

    if not sections:
        print("未识别到任何一级章节，请检查 PDF 格式或调整章节匹配规则。")
        sys.exit(1)

    # 使用 pypdf 读取原始 PDF，用于按页复制
    reader = PdfReader(pdf_path)

    print(f"\n开始写入拆分 PDF 到：{output_path.resolve()}")
    for index, section in enumerate(sections, start=1):
        filename = f"{index:03d}_{sanitize_filename(section['title'])}.pdf"
        file_path = output_path / filename

        start_idx = section["start_page_index"]
        end_idx = section["end_page_index"]
        page_count = end_idx - start_idx + 1

        write_section_pdf(reader, start_idx, end_idx, file_path)

        print(
            f"  [{index:03d}] {filename}"
            f"  (原书第 {start_idx + 1}–{end_idx + 1} 页，共 {page_count} 页)"
        )

    print(f"\n✅ 完成！共生成 {len(sections)} 个 PDF 文件。")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 PDF 书籍按一级章节拆分为多个 PDF 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  python pdf_splitter.py book.pdf
  python pdf_splitter.py book.pdf -o ./output
  python pdf_splitter.py /path/to/book.pdf -o /path/to/output_dir
        """,
    )
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出目录路径（默认：与 PDF 同目录下的同名文件夹加 _split 后缀）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    pdf_input_path = args.pdf_path
    if args.output:
        output_directory = args.output
    else:
        pdf_stem = Path(pdf_input_path).stem
        output_directory = str(Path(pdf_input_path).parent / f"{pdf_stem}_split")

    split_pdf_by_chapters(pdf_input_path, output_directory)
