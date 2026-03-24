"""
Markdown 题库解析模块
支持两种题目格式：
  格式1（如 006_1_exam.md）：**题目N：** 题干
  格式2（如 030_21_exam.md）：### 题目N：题干
"""

import os
import re
from typing import Optional


EXAM_QUESTIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "exam_questions")


def get_exam_questions_dir() -> str:
    env_dir = os.environ.get("EXAM_QUESTIONS_DIR")
    if env_dir:
        return os.path.abspath(env_dir)
    return os.path.abspath(EXAM_QUESTIONS_DIR)


def list_exam_files() -> list[dict]:
    """列出所有考试文件，返回章节列表（按文件名排序）"""
    questions_dir = get_exam_questions_dir()
    exam_files = []

    for filename in sorted(os.listdir(questions_dir)):
        # 只处理 *_exam.md 文件，排除 *_exam_questions.md
        if not filename.endswith("_exam.md"):
            continue
        filepath = os.path.join(questions_dir, filename)
        chapter_title = extract_chapter_title(filepath)
        exam_files.append({
            "file_id": filename.replace(".md", ""),
            "filename": filename,
            "title": chapter_title,
        })

    return exam_files


def extract_chapter_title(filepath: str) -> str:
    """从文件中提取一级标题（# 标题）"""
    with open(filepath, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    return os.path.basename(filepath)


def parse_exam_file(file_id: str) -> Optional[dict]:
    """
    解析单个考试文件，返回结构化数据：
    {
        "file_id": str,
        "title": str,
        "sections": [
            {
                "section_id": str,
                "title": str,
                "questions": [
                    {
                        "question_id": str,
                        "number": int,
                        "stem": str,
                        "options": ["A. ...", "B. ...", ...],
                        "answer": str,
                        "explanation": str,
                    }
                ]
            }
        ]
    }
    """
    questions_dir = get_exam_questions_dir()
    filepath = os.path.join(questions_dir, f"{file_id}.md")

    if not os.path.exists(filepath):
        return None

    with open(filepath, "r", encoding="utf-8") as file:
        content = file.read()

    return parse_markdown_content(file_id, content)


def parse_markdown_content(file_id: str, content: str) -> dict:
    """解析 Markdown 内容为结构化数据"""
    lines = content.split("\n")

    chapter_title = ""
    sections = []
    current_section = None
    current_question_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # 提取一级标题（章节名）
        if stripped.startswith("# ") and not stripped.startswith("## "):
            chapter_title = stripped[2:].strip()
            continue

        # 提取二级标题（子章节）
        if stripped.startswith("## "):
            # 保存上一道题
            if current_section is not None and current_question_lines:
                question = parse_question_block(
                    current_question_lines,
                    file_id,
                    current_section["section_id"],
                    len(current_section["questions"]) + 1,
                )
                if question:
                    current_section["questions"].append(question)
                current_question_lines = []

            section_title = stripped[3:].strip()
            section_index = len(sections) + 1
            current_section = {
                "section_id": f"{file_id}_s{section_index}",
                "title": section_title,
                "questions": [],
            }
            sections.append(current_section)
            continue

        # 分隔符：保存当前题目块
        if stripped == "---":
            if current_section is not None and current_question_lines:
                question = parse_question_block(
                    current_question_lines,
                    file_id,
                    current_section["section_id"],
                    len(current_section["questions"]) + 1,
                )
                if question:
                    current_section["questions"].append(question)
                current_question_lines = []
            continue

        # 收集题目行
        if current_section is not None:
            current_question_lines.append(line)

    # 处理最后一道题（文件末尾没有 --- 的情况）
    if current_section is not None and current_question_lines:
        question = parse_question_block(
            current_question_lines,
            file_id,
            current_section["section_id"],
            len(current_section["questions"]) + 1,
        )
        if question:
            current_section["questions"].append(question)

    return {
        "file_id": file_id,
        "title": chapter_title,
        "sections": sections,
    }


# 匹配题目开头的正则（两种格式）
# 格式1: **题目N：** 或 **N. **
# 格式2: ### 题目N：
QUESTION_START_PATTERNS = [
    re.compile(r"^\*\*题目\s*\d+[：:]\*\*"),          # **题目1：**
    re.compile(r"^###\s*题目\s*\d+[：:]"),             # ### 题目1：
    re.compile(r"^\*\*\d+\.\s"),                       # **1. 题干
    re.compile(r"^\d+\.\s+\*\*"),                      # 1. **题干
]

ANSWER_PATTERNS = [
    re.compile(r"\*\*正确答案[：:]\*\*\s*([A-Da-d])"),   # **正确答案：** A
    re.compile(r"\*\*正确答案[：:]\s*([A-Da-d])\*\*"),   # **正确答案：A**
    re.compile(r"正确答案[：:]\s*([A-Da-d])"),            # 正确答案：A
]

EXPLANATION_PATTERNS = [
    re.compile(r"\*\*解析[：:]\*\*\s*(.+)"),             # **解析：** 内容
    re.compile(r"\*\*解析[：:]\s*(.+?)\*\*"),             # **解析：内容**
    re.compile(r"解析[：:]\s*(.+)"),                      # 解析：内容
]

OPTION_PATTERN = re.compile(r"^([A-Da-d])[.．、。]\s*(.+)")


def is_question_start(line: str) -> bool:
    """判断一行是否是题目开头"""
    stripped = line.strip()
    return any(pattern.match(stripped) for pattern in QUESTION_START_PATTERNS)


def extract_question_stem(line: str) -> str:
    """从题目开头行提取题干（去掉题号前缀）"""
    stripped = line.strip()
    # 去掉 ### 题目N：
    stripped = re.sub(r"^###\s*题目\s*\d+[：:]\s*", "", stripped)
    # 去掉 **题目N：**
    stripped = re.sub(r"^\*\*题目\s*\d+[：:]\*\*\s*", "", stripped)
    # 去掉 **N. 
    stripped = re.sub(r"^\*\*\d+\.\s*", "", stripped)
    # 去掉末尾的 **
    stripped = stripped.rstrip("*").strip()
    return stripped


def parse_question_block(
    lines: list[str],
    file_id: str,
    section_id: str,
    question_number: int,
) -> Optional[dict]:
    """将一个题目的行列表解析为结构化题目对象"""
    if not lines:
        return None

    stem_lines: list[str] = []
    options: list[str] = []
    answer = ""
    explanation_lines: list[str] = []

    state = "stem"  # stem -> options -> answer -> explanation

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        # 检测选项行
        option_match = OPTION_PATTERN.match(stripped)
        if option_match and state in ("stem", "options"):
            state = "options"
            options.append(stripped)
            continue

        # 检测答案行
        answer_found = False
        for pattern in ANSWER_PATTERNS:
            match = pattern.search(stripped)
            if match:
                answer = match.group(1).upper()
                state = "answer"
                answer_found = True
                break
        if answer_found:
            continue

        # 检测解析行
        explanation_found = False
        for pattern in EXPLANATION_PATTERNS:
            match = pattern.search(stripped)
            if match:
                explanation_lines.append(match.group(1).strip())
                state = "explanation"
                explanation_found = True
                break
        if explanation_found:
            continue

        # 根据当前状态收集内容
        if state == "stem":
            stem_lines.append(stripped)
        elif state == "explanation":
            explanation_lines.append(stripped)

    # 清理题干：去掉题号前缀
    raw_stem = " ".join(stem_lines).strip()
    stem = extract_question_stem(raw_stem) if raw_stem else ""

    # 如果没有题干，说明这个块不是有效题目
    if not stem and not options:
        return None

    explanation = " ".join(explanation_lines).strip()
    # 去掉解析中的 markdown 加粗标记
    explanation = re.sub(r"\*\*", "", explanation).strip()

    question_id = f"{section_id}_q{question_number}"

    return {
        "question_id": question_id,
        "number": question_number,
        "stem": stem,
        "options": options,
        "answer": answer,
        "explanation": explanation,
    }
