#!/usr/bin/env python3
"""
PDF 书籍章节拆分工具
将 PDF 文件按一级标题拆分成多个 Markdown 文件，
同一一级标题下的所有内容（含子章节）合并到同一文件。
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


def extract_pages_with_structure(pdf_path: str) -> list[dict]:
    """
    使用 pdfplumber 提取每页的文字块及字体信息。
    返回结构：[{"page_num": int, "blocks": [{"text": str, "font_sizes": [float]}]}]
    """
    pages_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            words = page.extract_words(extra_attrs=["size"])
            if not words:
                pages_data.append({"page_num": page_index + 1, "blocks": []})
                continue

            # 计算页面平均字号
            all_sizes = [word.get("size", 0) for word in words if word.get("size")]
            page_avg_font_size = sum(all_sizes) / len(all_sizes) if all_sizes else 0

            # 将相邻的词按行分组（y 坐标相近视为同一行，阈值放宽到 5 以兼容更多 PDF）
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

            pages_data.append({"page_num": page_index + 1, "blocks": blocks})

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


def split_into_h1_sections(pages_data: list[dict]) -> list[dict]:
    """
    将页面数据按一级标题聚合为章节。
    同一一级标题下的所有内容（正文 + 子标题）合并到同一章节。

    每个章节的 content_items 是一个列表，元素为：
        {"kind": "h2" | "text", "text": str}

    返回：
        [
            {
                "title": str,           # 一级标题文本
                "start_page": int,
                "content_items": list[dict],
            }
        ]
    """
    doc_heading_sizes = collect_doc_heading_sizes(pages_data)

    sections: list[dict] = []
    current_title = "前言"
    current_items: list[dict] = []
    start_page = 1

    for page_info in pages_data:
        page_num = page_info["page_num"]
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
                # 保存上一个一级章节（有内容才保存）
                if current_items:
                    sections.append({
                        "title": current_title,
                        "start_page": start_page,
                        "content_items": current_items,
                    })
                # 开始新的一级章节
                current_title = text
                current_items = []
                start_page = page_num

            elif level == 2:
                # 二级标题作为内容项保留，渲染为 ##
                current_items.append({"kind": "h2", "text": text})

            else:
                # 普通正文
                current_items.append({"kind": "text", "text": text})

    # 保存最后一个章节
    if current_items:
        sections.append({
            "title": current_title,
            "start_page": start_page,
            "content_items": current_items,
        })

    return sections


def sanitize_filename(title: str) -> str:
    """将章节标题转换为合法的文件名。"""
    # 替换不合法的文件名字符
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', title)
    # 去除首尾空白
    sanitized = sanitized.strip().strip('.')
    # 限制文件名长度
    return sanitized[:80] if sanitized else "untitled"


def section_to_markdown(section: dict) -> str:
    """
    将一级章节数据转换为 Markdown 格式文本。

    - 一级标题用 `#`
    - 二级标题用 `##`
    - 连续正文行合并为段落，段落间空一行
    """
    output_lines = [f"# {section['title']}", ""]

    pending_text_lines: list[str] = []

    def flush_paragraph() -> None:
        if pending_text_lines:
            output_lines.append(" ".join(pending_text_lines))
            output_lines.append("")
            pending_text_lines.clear()

    for item in section["content_items"]:
        if item["kind"] == "h2":
            flush_paragraph()
            output_lines.append(f"## {item['text']}")
            output_lines.append("")
        else:
            stripped = item["text"].strip()
            if stripped:
                pending_text_lines.append(stripped)
            else:
                flush_paragraph()

    flush_paragraph()

    return "\n".join(output_lines)


def pdf_parser_chapters(pdf_path: str, output_dir: str) -> None:
    """
    主函数：读取 PDF，按一级标题聚合章节，保存为多个 Markdown 文件。
    同一一级标题下的所有内容（含子章节）写入同一个文件。
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
    pages_data = extract_pages_with_structure(pdf_path)
    print(f"共读取 {len(pages_data)} 页")

    print("正在识别章节结构（按一级标题聚合）...")
    sections = split_into_h1_sections(pages_data)
    print(f"共识别出 {len(sections)} 个一级章节")

    if not sections:
        print("未识别到任何一级章节，请检查 PDF 格式或调整章节匹配规则。")
        sys.exit(1)

    print(f"\n开始写入 Markdown 文件到：{output_path.resolve()}")
    for index, section in enumerate(sections, start=1):
        filename = f"{index:03d}_{sanitize_filename(section['title'])}.md"
        file_path = output_path / filename
        markdown_content = section_to_markdown(section)

        with open(file_path, "w", encoding="utf-8") as markdown_file:
            markdown_file.write(markdown_content)

        h2_count = sum(1 for item in section["content_items"] if item["kind"] == "h2")
        print(f"  [{index:03d}] {filename}  (起始页: {section['start_page']}, 子章节: {h2_count})")

    print(f"\n✅ 完成！共生成 {len(sections)} 个 Markdown 文件。")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 PDF 书籍按章节拆分为多个 Markdown 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  python pdf_parser.py book.pdf
  python pdf_parser.py book.pdf -o ./output
  python pdf_parser.py /path/to/book.pdf -o /path/to/output_dir
        """,
    )
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出目录路径（默认：与 PDF 同目录下的同名文件夹）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    pdf_input_path = args.pdf_path
    if args.output:
        output_directory = args.output
    else:
        pdf_stem = Path(pdf_input_path).stem
        output_directory = str(Path(pdf_input_path).parent / pdf_stem)

    pdf_parser_chapters(pdf_input_path, output_directory)
