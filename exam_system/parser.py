import os
import re
from typing import List, Dict, Any

# Pre-compiled regex patterns for better performance
TITLE_PATTERN = re.compile(r'^#\s+(.+)$|^##\s+(.+)$', re.MULTILINE)
SECTION_PATTERN = re.compile(r'(##|#)\s*(.+?)(?=\n#|\Z)', re.DOTALL)
QUESTION_FORMAT_1_PATTERN = re.compile(
    r'\*\*题目\d+：\*\*\s*(.*?)\n((?:[A-Z]\.\s*[^\n]+\n?)+)\s*\*\*正确答案：\s*\*\*\s*([A-Z])\s*\*\*解析：\s*\*\*\s*(.*?)(?=\n\*\*题目\d+：\*\*|$)',
    re.DOTALL
)
QUESTION_FORMAT_2_PATTERN = re.compile(
    r'###\s*题目\d+：\s*(.*?)\n((?:[A-Z]\.\s*[^\n]+\n?)+)\s*\*\*正确答案：\s*([A-Z])\s*\*\*解析：\s*\*\*\s*(.*?)(?=\n###\s*题目\d+：|$)',
    re.DOTALL
)
OPTION_LETTER_PATTERN = re.compile(r'^[A-Z]\.')
SEPARATOR_PATTERN = re.compile(r'-{3,}\n?')


def list_exam_files(exam_dir=None):
    """List all exam markdown files in the specified directory"""
    if exam_dir is None:
        exam_dir = os.getenv("EXAM_QUESTIONS_DIR", "../exam_questions")
    
    if not os.path.exists(exam_dir):
        return []
    
    files = []
    for filename in sorted(os.listdir(exam_dir)):
        if filename.endswith('.md'):
            file_id = os.path.splitext(filename)[0]
            files.append({
                "filename": filename,
                "file_id": file_id
            })
    return files

def parse_exam_file(file_id, exam_type="regular"):
    """Parse exam file by file ID and exam type"""
    exam_dir = os.getenv("EXAM_QUESTIONS_DIR", "../exam_questions")
    file_path = os.path.join(exam_dir, f"{file_id}.md")
    if not os.path.exists(file_path):
        return None
    
    return parse_exam_file_content(file_path, exam_type)

def parse_exam_file_content(file_path: str, exam_type: str = "regular") -> Dict[str, Any]:
    """Parse exam file content and return structured data"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract the first heading as title
    title_match = TITLE_PATTERN.search(content)
    title = title_match.group(1) if title_match and title_match.group(1) else (
        title_match.group(2) if title_match and title_match.group(2) else 
        os.path.basename(file_path)
    ).strip()
    
    # Split content by section headers
    sections = []
    
    # Match section headers (## or ###) and their content
    section_matches = list(SECTION_PATTERN.finditer(content))
    
    for i, match in enumerate(section_matches):
        section_header = match.group(2).strip()
        
        # Determine section content
        start_pos = match.end()
        end_pos = section_matches[i+1].start() if i+1 < len(section_matches) else len(content)
        section_content = content[start_pos:end_pos].strip()
        
        # Parse questions in this section - extract filename without extension
        file_name_no_ext = os.path.splitext(os.path.basename(file_path))[0]
        section_id_prefix = f"{exam_type}_{file_name_no_ext}_s{len(sections)+1}"
        questions = parse_questions_from_content(section_content, exam_type, section_id_prefix)
        
        if questions:  # Only add section if it has questions
            sections.append({
                "title": section_header,
                "questions": questions,
                "section_id": section_id_prefix
            })
    
    # If no sections were identified, treat entire file as one section
    if not sections:
        file_name_no_ext = os.path.splitext(os.path.basename(file_path))[0]
        questions = parse_questions_from_content(content, exam_type, f"{exam_type}_{file_name_no_ext}_s1")
        if questions:
            sections.append({
                "title": title,
                "questions": questions,
                "section_id": f"{exam_type}_{file_name_no_ext}_s1"
            })
    
    return {
        "title": title,
        "sections": sections
    }

def parse_questions_from_content(content: str, exam_type: str, section_id: str) -> List[Dict[str, Any]]:
    """Parse questions from content string"""
    # Split content into potential questions using pre-compiled separator pattern
    question_blocks = SEPARATOR_PATTERN.split(content)
    
    questions = []
    question_number = 1
    
    for block in question_blocks:
        block = block.strip()
        if not block:
            continue
            
        # Try different patterns for different question formats using pre-compiled regex
        question_data = parse_question_format_1(block, exam_type, section_id, question_number) or \
                       parse_question_format_2(block, exam_type, section_id, question_number)
        
        if question_data:
            questions.append(question_data)
            question_number += 1
    
    return questions

def parse_question_format_1(content: str, exam_type: str, section_id: str, number: int) -> Dict[str, Any] or None:
    """Parse first question format: **题目 X：** 题干内容"""
    # Use pre-compiled pattern
    matches = QUESTION_FORMAT_1_PATTERN.findall(content)
    
    if not matches:
        return None
    
    for i, match in enumerate(matches):
        stem, options_str, answer, explanation = match
        stem = stem.strip()
        explanation = explanation.strip()
        
        # Parse options
        options = []
        option_lines = [line.strip() for line in options_str.split('\n')]
        for opt_line in option_lines:
            if OPTION_LETTER_PATTERN.match(opt_line):
                options.append(opt_line)
        
        if options and answer:
            return {
                "question_id": f"{section_id}_q{number}",
                "number": number,
                "stem": stem,
                "options": options,
                "answer": answer,
                "explanation": explanation
            }
    
    return None

def parse_question_format_2(content: str, exam_type: str, section_id: str, number: int) -> Dict[str, Any] or None:
    """Parse second question format: ### 题目 X：题干内容"""
    # Use pre-compiled pattern
    matches = QUESTION_FORMAT_2_PATTERN.findall(content)
    
    if not matches:
        return None
    
    for i, match in enumerate(matches):
        stem, options_str, answer, explanation = match
        stem = stem.strip()
        explanation = explanation.strip()
        
        # Parse options
        options = []
        option_lines = [line.strip() for line in options_str.split('\n')]
        for opt_line in option_lines:
            if OPTION_LETTER_PATTERN.match(opt_line):
                options.append(opt_line)
        
        if options and answer:
            return {
                "question_id": f"{section_id}_q{number}",
                "number": number,
                "stem": stem,
                "options": options,
                "answer": answer,
                "explanation": explanation
            }
    
    return None