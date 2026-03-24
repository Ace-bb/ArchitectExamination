"""
PDF 考题解析器
将 past_year_exam/ 目录下的 PDF 考试文件解析为 Markdown 格式
- 文字内容按原始结构保留
- 图片提取并保存为 PNG，在 Markdown 中以 ![图片](images/xxx.png) 引用
- 输出到 exam_md/ 目录
"""

import os
import re
import sys

import fitz  # pymupdf


PDF_PATH = os.path.join(
    os.path.dirname(__file__),
    "past_year_exam",
    "2009年系统架构师考试科目一：综合知识.pdf",
)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "exam_md")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")


def ensure_directories(output_dir, image_dir) -> None:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(image_dir, exist_ok=True)


def extract_images_from_page(
    page: fitz.Page,
    doc: fitz.Document,
    page_number: int,
    image_counter: list[int],
    image_dir: str = IMAGES_DIR,
) -> dict[int, str]:
    """
    提取页面中的所有图片，保存为 PNG 文件。
    返回 { xref: 相对路径 } 的映射，供后续插入 Markdown 使用。
    """
    xref_to_relative_path: dict[int, str] = {}
    image_list = page.get_images(full=True)

    for image_info in image_list:
        xref = image_info[0]
        image_counter[0] += 1
        image_filename = f"page{page_number:02d}_img{image_counter[0]:03d}.png"
        image_save_path = os.path.join(image_dir, image_filename)
        relative_path = f"images/{image_filename}"

        try:
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            with open(image_save_path, "wb") as image_file:
                image_file.write(image_bytes)
            xref_to_relative_path[xref] = relative_path
            print(f"  [图片] 保存: {image_filename}")
        except Exception as error:
            print(f"  [警告] 提取图片 xref={xref} 失败: {error}")

    return xref_to_relative_path


def get_page_image_positions(page: fitz.Page) -> list[dict]:
    """
    获取页面中所有图片的位置信息（bbox），用于在文字流中插入图片引用。
    返回按垂直位置排序的图片列表：[{ xref, bbox_top, bbox_bottom }]
    """
    image_positions = []
    image_list = page.get_images(full=True)

    for image_info in image_list:
        xref = image_info[0]
        # 通过 get_image_rects 获取图片在页面上的位置
        rects = page.get_image_rects(xref)
        for rect in rects:
            image_positions.append({
                "xref": xref,
                "bbox_top": rect.y0,
                "bbox_bottom": rect.y1,
                "rect": rect,
            })

    # 按垂直位置排序
    image_positions.sort(key=lambda item: item["bbox_top"])
    return image_positions


def build_page_markdown(
    page: fitz.Page,
    xref_to_relative_path: dict[int, str],
    page_number: int,
) -> str:
    """
    将一页 PDF 的文字和图片合并为 Markdown 文本。
    策略：按文字块的垂直位置，在合适位置插入图片引用。
    每页最靠上的第一张图片为 logo，自动跳过不输出。
    """
    # 获取带位置信息的文字块
    text_blocks = page.get_text("blocks")  # [(x0,y0,x1,y1,text,block_no,block_type)]
    # block_type: 0=文字, 1=图片

    image_positions = get_page_image_positions(page)

    # 每页最靠上的第一张图片为 logo，记录其 xref 以便后续跳过
    logo_xref: int | None = image_positions[0]["xref"] if image_positions else None

    # 合并文字块和图片块，按垂直位置排序
    elements: list[dict] = []

    for block in text_blocks:
        block_type = block[6]
        if block_type == 0:  # 文字块
            elements.append({
                "type": "text",
                "top": block[1],
                "bottom": block[3],
                "content": block[4],
            })
        elif block_type == 1:  # PDF 内嵌图片块（通过 blocks 检测到的）
            # 找到对应的 xref
            for image_pos in image_positions:
                # 位置匹配（允许小误差）
                if abs(image_pos["bbox_top"] - block[1]) < 5:
                    xref = image_pos["xref"]
                    # 跳过 logo 图片
                    if xref == logo_xref:
                        break
                    if xref in xref_to_relative_path:
                        elements.append({
                            "type": "image",
                            "top": block[1],
                            "xref": xref,
                            "path": xref_to_relative_path[xref],
                        })
                    break

    # 对于通过 get_images 找到但 blocks 中未出现的图片，也要插入
    inserted_xrefs = {elem["xref"] for elem in elements if elem["type"] == "image"}
    for image_pos in image_positions:
        xref = image_pos["xref"]
        # 跳过 logo 图片
        if xref == logo_xref:
            continue
        if xref not in inserted_xrefs and xref in xref_to_relative_path:
            elements.append({
                "type": "image",
                "top": image_pos["bbox_top"],
                "xref": xref,
                "path": xref_to_relative_path[xref],
            })
            inserted_xrefs.add(xref)

    # 按垂直位置排序
    elements.sort(key=lambda elem: elem["top"])

    # 构建 Markdown 内容
    markdown_lines: list[str] = []

    for element in elements:
        if element["type"] == "text":
            text = element["content"].strip()
            if not text:
                continue
            # 清理页眉（QQ群信息和页码行）
            cleaned_lines = []
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("QQ 群") or stripped.startswith("QQ群"):
                    continue
                if re.match(r"^第\s*\d+\s*页\s*共\s*\d+\s*页$", stripped):
                    continue
                cleaned_lines.append(line)
            cleaned_text = "\n".join(cleaned_lines).strip()
            if cleaned_text:
                markdown_lines.append(cleaned_text)
                markdown_lines.append("")  # 段落间空行

        elif element["type"] == "image":
            image_path = element["path"]
            markdown_lines.append(f"![图片]({image_path})")
            markdown_lines.append("")

    return "\n".join(markdown_lines)


def join_text_lines(lines: list[str]) -> str:
    """
    将多行文本合并为一行。
    中文字符结尾的行与下一行之间直接拼接（无需空格），
    英文/数字结尾的行与下一行之间加一个空格，避免断词。
    """
    if not lines:
        return ""
    result = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not result:
            result = stripped
            continue
        # 判断上一段末尾字符是否为中文或中文标点
        last_char = result[-1]
        is_last_cjk = "\u4e00" <= last_char <= "\u9fff" or last_char in "，。！？；：、""''（）【】"
        # 判断当前行首字符是否为中文
        first_char = stripped[0]
        is_first_cjk = "\u4e00" <= first_char <= "\u9fff" or first_char in "，。！？；：、""''（）【】"
        if is_last_cjk or is_first_cjk:
            result += stripped
        else:
            result += " " + stripped
    return result


def is_question_start(line: str) -> re.Match | None:
    """判断一行是否为题目编号行，如 '1.' '25.' 开头，返回匹配对象或 None。"""
    return re.match(r"^(\d+)\.\s*(.*)", line.strip())


def is_option_line(line: str) -> bool:
    """判断一行是否为选项行，如 'A．xxx' 'B．xxx' 'A. xxx' 等。"""
    return bool(re.match(r"^[A-Da-d][．.。、]\s*\S", line.strip()))


def extract_answer_letter(answer_text: str) -> str:
    """从【答案】文本中提取答案字母，如 'B。' -> 'B'，'A、C、B。' -> 'A、C、B'。"""
    # 去掉【答案】前缀和末尾标点
    cleaned = re.sub(r"^【答案】\s*", "", answer_text.strip())
    cleaned = cleaned.rstrip("。.")
    return cleaned.strip()


def extract_analysis_text(analysis_text: str) -> str:
    """从【解析】文本中提取解析内容（去掉【解析】标签本身）。"""
    return re.sub(r"^【解析】\s*", "", analysis_text.strip()).strip()


def format_question_block(
    question_number: int,
    question_lines: list[str],
    option_lines: list[str],
    analysis_lines: list[str],
    answer_text: str,
    image_lines: list[str],
) -> str:
    """
    将一道题的各部分组装为目标格式：
    **题目N：** 题干内容

    （图片，如有）

    A. 选项A
    B. 选项B
    ...

    **正确答案：** X
    **解析：** 解析内容
    """
    # 题干：合并多行，中文行之间直接拼接（无需空格），去掉末尾括号占位符
    question_body = join_text_lines(question_lines)
    question_body = re.sub(r"[（(]\s*[）)]\s*$", "", question_body).strip()

    result_parts: list[str] = []

    # 题目标题行
    result_parts.append(f"**题目{question_number}：** {question_body}")
    result_parts.append("")

    # 题目中的图片
    for image_line in image_lines:
        result_parts.append(image_line)
        result_parts.append("")

    # 选项
    for option_line in option_lines:
        # 统一选项格式：将 A．/A。/A、 统一为 A.
        normalized = re.sub(r"^([A-Da-d])[．.。、]\s*", lambda m: f"{m.group(1).upper()}. ", option_line.strip())
        result_parts.append(normalized)
    result_parts.append("")

    # 正确答案
    answer_letter = extract_answer_letter(answer_text) if answer_text else "（未提供）"
    result_parts.append(f"**正确答案：** {answer_letter}")

    # 解析
    analysis_body = join_text_lines(analysis_lines)
    analysis_body = extract_analysis_text(analysis_body) if analysis_body else ""
    if analysis_body:
        result_parts.append(f"**解析：** {analysis_body}")

    result_parts.append("")
    result_parts.append("---")
    result_parts.append("")

    return "\n".join(result_parts)


def clean_markdown_text(raw_text: str) -> str:
    """
    对整体原始 Markdown 文本做结构化重排：
    将每道题解析为 题干 + 选项 + 正确答案 + 解析 的标准格式。
    """
    # 先合并多余空行，方便后续逐行处理
    raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)

    lines = raw_text.split("\n")

    # 状态机：逐行扫描，识别题目边界和各部分
    output_parts: list[str] = []
    # 文档标题（第一行 # 开头）单独保留
    header_lines: list[str] = []
    content_start_index = 0
    for index, line in enumerate(lines):
        if line.startswith("#"):
            header_lines.append(line)
            content_start_index = index + 1
        elif header_lines:
            # 标题后的第一个非空行开始正文
            break

    if header_lines:
        output_parts.append("\n".join(header_lines))
        output_parts.append("")

    # 当前题目的各部分缓冲
    current_question_number: int | None = None
    current_question_lines: list[str] = []
    current_option_lines: list[str] = []
    current_image_lines: list[str] = []  # 题目中的图片（在选项之前出现的）
    current_analysis_lines: list[str] = []
    current_answer_text: str = ""

    # 解析状态
    STATE_QUESTION = "question"   # 正在读题干
    STATE_OPTIONS = "options"     # 正在读选项
    STATE_ANALYSIS = "analysis"   # 正在读解析
    STATE_ANSWER = "answer"       # 已读到答案行
    current_state = STATE_QUESTION

    # 跳过文档标题行和紧随其后的重复标题文字行
    skip_until_first_question = True

    def flush_current_question() -> None:
        """将当前缓冲的题目数据格式化并加入输出。"""
        if current_question_number is None:
            return
        formatted = format_question_block(
            question_number=current_question_number,
            question_lines=current_question_lines,
            option_lines=current_option_lines,
            analysis_lines=current_analysis_lines,
            answer_text=current_answer_text,
            image_lines=current_image_lines,
        )
        output_parts.append(formatted)

    for line in lines[content_start_index:]:
        stripped = line.strip()

        # 跳过分隔线
        if stripped == "---":
            continue

        # 跳过空行（状态机自行处理段落）
        if not stripped:
            continue

        # 跳过页眉垃圾行
        if stripped.startswith("QQ 群") or stripped.startswith("QQ群"):
            continue
        if re.match(r"^第\s*\d+\s*页\s*共\s*\d+\s*页$", stripped):
            continue
        # 跳过版权声明行
        if stripped in ("仅供个人学习", "请勿用于任何商业用途"):
            continue

        # 检测是否为新题目开始
        question_match = is_question_start(stripped)
        if question_match:
            # 在遇到第一道题之前，跳过文档重复标题等无关内容
            skip_until_first_question = False

            # 保存上一道题
            flush_current_question()

            # 重置缓冲
            current_question_number = int(question_match.group(1))
            first_line_content = question_match.group(2).strip()
            current_question_lines = [first_line_content] if first_line_content else []
            current_option_lines = []
            current_image_lines = []
            current_analysis_lines = []
            current_answer_text = ""
            current_state = STATE_QUESTION
            continue

        if skip_until_first_question:
            continue

        # 图片行：根据当前状态决定归属
        if stripped.startswith("!["):
            if current_state == STATE_QUESTION:
                current_image_lines.append(stripped)
            # 选项/解析阶段的图片暂时忽略（通常不会有）
            continue

        # 答案行
        if stripped.startswith("【答案】"):
            current_answer_text = stripped
            current_state = STATE_ANSWER
            continue

        # 解析行
        if stripped.startswith("【解析】"):
            analysis_content = re.sub(r"^【解析】\s*", "", stripped).strip()
            current_analysis_lines = [analysis_content] if analysis_content else []
            current_state = STATE_ANALYSIS
            continue

        # 选项行
        if is_option_line(stripped):
            current_option_lines.append(stripped)
            current_state = STATE_OPTIONS
            continue

        # 其他行：根据当前状态追加到对应缓冲
        if current_state == STATE_QUESTION:
            current_question_lines.append(stripped)
        elif current_state == STATE_OPTIONS:
            # 选项后的非选项行，可能是多选题的子题干，追加到选项末尾
            current_option_lines.append(stripped)
        elif current_state == STATE_ANALYSIS:
            current_analysis_lines.append(stripped)
        elif current_state == STATE_ANSWER:
            # 答案后的内容归入解析
            current_analysis_lines.append(stripped)
            current_state = STATE_ANALYSIS

    # 保存最后一道题
    flush_current_question()

    return "\n".join(output_parts)


def parse_pdf_to_markdown(pdf_path: str) -> None:
    """主函数：解析 PDF 并输出 Markdown 文件"""
    # ensure_directories()

    print(f"正在解析: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    print(f"共 {total_pages} 页")

    pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]
    output_md_path = os.path.join(OUTPUT_DIR, f"{pdf_filename}", f"{pdf_filename}.md")
    output_img_dir = os.path.join(OUTPUT_DIR, f"{pdf_filename}", "images")
    ensure_directories(output_dir=os.path.dirname(output_md_path), image_dir=output_img_dir)
    all_markdown_parts: list[str] = []
    # 添加文档标题
    all_markdown_parts.append(f"# {pdf_filename}\n")

    image_counter = [0]  # 使用列表以便在函数内修改

    # 先提取所有页的图片，并将所有页的原始文本拼接为一个连续文本流
    # 这样可以正确处理跨页的答案/解析归属问题（如答案在下一页开头）
    all_page_texts: list[str] = []

    for page_number in range(1, total_pages + 1):
        page = doc[page_number - 1]
        print(f"\n处理第 {page_number}/{total_pages} 页...")

        # 提取并保存图片
        xref_to_relative_path = extract_images_from_page(
            page, doc, page_number, image_counter, output_img_dir
        )

        # 构建该页的原始文本（含图片引用），不加页面分隔符
        page_markdown = build_page_markdown(page, xref_to_relative_path, page_number)
        if page_markdown.strip():
            all_page_texts.append(page_markdown)

    doc.close()

    # 将所有页文本合并为一个连续流，再做结构化解析
    # 页间不插入 --- 分隔线，避免干扰跨页题目的答案归属
    raw_full_text = f"# {pdf_filename}\n\n" + "\n".join(all_page_texts)
    structured_markdown = clean_markdown_text(raw_full_text)

    # 写入文件
    with open(output_md_path, "w", encoding="utf-8") as output_file:
        output_file.write(structured_markdown)

    print(f"\n✅ 解析完成！")
    print(f"   Markdown 文件: {output_md_path}")
    print(f"   图片目录: {IMAGES_DIR}")
    print(f"   共提取图片: {image_counter[0]} 张")


if __name__ == "__main__":
    default_pdf_dir = os.path.join(os.path.dirname(__file__), "past_year_exam")
    target_dir = "历年真题"

    if not os.path.isdir(target_dir):
        print(f"❌ 找不到目录: {target_dir}")
        sys.exit(1)

    matched_pdf_paths: list[str] = []
    for root, _, files in os.walk(target_dir):
        for filename in files:
            if filename.lower().endswith(".pdf") and "综合知识" in filename:
                matched_pdf_paths.append(os.path.join(root, filename))

    matched_pdf_paths.sort()

    if not matched_pdf_paths:
        print(f"⚠️ 在目录中未找到文件名包含“综合知识”的 PDF: {target_dir}")
        sys.exit(0)

    print(f"将在目录中处理 {len(matched_pdf_paths)} 个“综合知识”PDF 文件")
    for index, pdf_path in enumerate(matched_pdf_paths, start=1):
        print(f"\n[{index}/{len(matched_pdf_paths)}] 开始处理: {pdf_path}")
        parse_pdf_to_markdown(pdf_path)
