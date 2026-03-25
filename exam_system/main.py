import json
import os
from typing import Optional, Dict, Any
from enum import Enum

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

from parser import list_exam_files, parse_exam_file

# Define exam types
class ExamType(str, Enum):
    regular = "regular"
    historical = "historical"

# Configurable directories
REGULAR_QUESTIONS_DIR = os.getenv("EXAM_QUESTIONS_DIR", "../exam_questions")
HISTORICAL_QUESTIONS_DIR = os.getenv("EXAM_HISTORICAL_DIR", "../exam_md")

# Map exam types to directories
EXAM_DIRS = {
    ExamType.regular: REGULAR_QUESTIONS_DIR,
    ExamType.historical: HISTORICAL_QUESTIONS_DIR
}

# Update the mistakes file path to support different exam types
def get_mistakes_file(exam_type: ExamType) -> str:
    filename = f"mistakes_{exam_type.value}.json"
    return os.path.join(os.path.dirname(__file__), filename)

def load_mistakes(exam_type: ExamType) -> dict:
    """From local file read mistake records, format: { question_id: count }"""
    mistakes_file = get_mistakes_file(exam_type)
    if not os.path.exists(mistakes_file):
        return {}
    with open(mistakes_file, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}

def save_mistakes(exam_type: ExamType, mistakes: dict) -> None:
    """Write mistake records to local file"""
    mistakes_file = get_mistakes_file(exam_type)
    with open(mistakes_file, "w", encoding="utf-8") as file:
        json.dump(mistakes, file, ensure_ascii=False, indent=2)

load_dotenv()

app = FastAPI(title="System Architect Practice System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory (frontend page)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    question_id: str
    question_stem: str
    options: list[str]
    answer: str
    explanation: str
    user_message: str
    history: list[dict] = []

class SaveMistakesRequest(BaseModel):
    exam_type: ExamType = ExamType.regular
    wrong_question_ids: list[str]


# ──────────────────────────────────────────────
# Exam Interface
# ──────────────────────────────────────────────

# Cache for exam file lists to avoid repeated directory scans
_exam_file_cache = {}

def list_exam_files_by_type(exam_type: ExamType):
    """List exam files based on exam type with caching"""
    # Return cached result if available
    if exam_type in _exam_file_cache:
        return _exam_file_cache[exam_type]
    
    exam_dir = EXAM_DIRS.get(exam_type)
    if not exam_dir or not os.path.exists(exam_dir):
        _exam_file_cache[exam_type] = []
        return []
    
    files = []
    
    # For historical exams, search recursively in subdirectories
    if exam_type == ExamType.historical:
        for root, dirs, filenames in os.walk(exam_dir):
            # Skip the images directory
            if 'images' in root:
                continue
            for filename in sorted(filenames):
                if filename.endswith('.md'):
                    # Use subdirectory name as file_id for historical exams
                    subdir_name = os.path.basename(root)
                    file_id = subdir_name
                    files.append({
                        "filename": filename,
                        "file_id": file_id,
                        "full_path": os.path.join(root, filename),
                        "exam_type": exam_type.value
                    })
    else:
        # For regular exams, just list files in the root directory
        for filename in sorted(os.listdir(exam_dir)):
            if filename.endswith('.md'):
                file_id = os.path.splitext(filename)[0]
                files.append({
                    "filename": filename,
                    "file_id": file_id,
                    "exam_type": exam_type.value
                })
    
    # Cache the result
    _exam_file_cache[exam_type] = files
    return files


# Cache for parsed exam files to avoid repeated parsing
_parsed_exam_cache = {}

def parse_exam_file_by_type(exam_type: ExamType, file_id: str):
    """Parse exam file based on exam type with caching"""
    # Create cache key
    cache_key = f"{exam_type.value}:{file_id}"
    
    # Return cached result if available
    if cache_key in _parsed_exam_cache:
        return _parsed_exam_cache[cache_key]
    
    exam_dir = EXAM_DIRS.get(exam_type)
    if not exam_dir:
        return None
    
    # For historical exams, file_id is the subdirectory name
    if exam_type == ExamType.historical:
        # Find the .md file in the subdirectory
        subdir_path = os.path.join(exam_dir, file_id)
        if not os.path.exists(subdir_path):
            return None
        
        # Look for .md file in this subdirectory
        md_files = [f for f in os.listdir(subdir_path) if f.endswith('.md')]
        if not md_files:
            return None
        
        # Use the first .md file found
        filename = md_files[0]
        file_path = os.path.join(subdir_path, filename)
    else:
        # For regular exams, file_id is the filename without extension
        file_path = os.path.join(exam_dir, f"{file_id}.md")
    
    if not os.path.exists(file_path):
        return None
    
    # Parse the file
    from parser import parse_exam_file_content
    result = parse_exam_file_content(file_path, exam_type.value)
    
    # Cache the result
    _parsed_exam_cache[cache_key] = result
    return result


@app.get("/api/exam-types")
def get_exam_types():
    """Get available exam types"""
    return {
        "exam_types": [
            {"value": "regular", "label": "章节练习"},
            {"value": "historical", "label": "历年真题"}
        ]
    }


@app.get("/api/chapters")
def get_chapters(exam_type: ExamType = ExamType.regular):
    """Get chapter list (tree structure) by exam type"""
    exam_files = list_exam_files_by_type(exam_type)
    chapters = []

    for exam_file in exam_files:
        file_id = exam_file["file_id"]
        parsed = parse_exam_file_by_type(exam_type, file_id)
        if not parsed:
            continue

        sections = []
        for section in parsed["sections"]:
            sections.append({
                "section_id": section["section_id"],
                "title": section["title"],
                "question_count": len(section["questions"]),
            })

        chapters.append({
            "file_id": file_id,
            "title": parsed["title"],
            "sections": sections,
            "exam_type": exam_type.value
        })

    return {"chapters": chapters}


@app.post("/api/cache/clear")
def clear_cache(exam_type: str = None):
    """
    Clear the exam file cache.
    If exam_type is provided, only clear that type's cache.
    Otherwise, clear all caches.
    """
    global _exam_file_cache, _parsed_exam_cache
    
    if exam_type:
        # Clear specific exam type cache
        exam_type_enum = ExamType(exam_type)
        _exam_file_cache.pop(exam_type_enum, None)
        # Clear parsed cache entries for this type
        keys_to_remove = [k for k in _parsed_exam_cache if k.startswith(f"{exam_type}:")]
        for key in keys_to_remove:
            del _parsed_exam_cache[key]
        return {"message": f"Cleared cache for exam type: {exam_type}"}
    else:
        # Clear all caches
        _exam_file_cache.clear()
        _parsed_exam_cache.clear()
        return {"message": "Cleared all caches"}


@app.get("/api/sections/{section_id}")
def get_section_questions(section_id: str, exam_type: ExamType = ExamType.regular):
    """
    Get all questions under a subsection.
    section_id format: {exam_type}_{file_id}_s{index}, e.g., regular_006_1_exam_s1
    """
    # Extract exam_type and file_id from section_id
    parts = section_id.split('_', 2)
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Invalid section_id format")
    
    extracted_exam_type = parts[0]
    file_part = '_'.join(parts[1:])  # Reconstruct the rest part
    # Now we need to split again to separate file_id from section index
    # section_id format: {exam_type}_{file_id}_s{index}
    file_section_parts = file_part.rsplit('_s', 1)
    if len(file_section_parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid section_id format")
        
    file_id = file_section_parts[0]

    parsed = parse_exam_file_by_type(ExamType(extracted_exam_type), file_id)
    if not parsed:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    target_section = None
    for section in parsed["sections"]:
        if section["section_id"] == section_id:
            target_section = section
            break

    if not target_section:
        raise HTTPException(status_code=404, detail=f"Subsection not found: {section_id}")

    return {
        "section_id": target_section["section_id"],
        "title": target_section["title"],
        "chapter_title": parsed["title"],
        "questions": target_section["questions"],
    }


# ──────────────────────────────────────────────
# Mistake Interface
# ──────────────────────────────────────────────

@app.get("/api/mistakes/{section_id}")
def get_section_mistakes(section_id: str, exam_type: ExamType = ExamType.regular):
    """
    Get historical error counts for questions under a subsection.
    Return: { question_id: count, ... } (only questions with error records)
    """
    all_mistakes = load_mistakes(exam_type)
    # Filter out mistakes belonging to this subsection (question_id starts with section_id)
    section_mistakes = {
        question_id: count
        for question_id, count in all_mistakes.items()
        if question_id.startswith(section_id)
    }
    return {"mistakes": section_mistakes}


@app.post("/api/mistakes")
def save_section_mistakes(request: SaveMistakesRequest):
    """
    Save incorrectly answered questions, cumulatively add error counts to local mistakes.json.
    """
    exam_type = request.exam_type
    if not request.wrong_question_ids:
        return {"saved": 0}

    all_mistakes = load_mistakes(exam_type)
    for question_id in request.wrong_question_ids:
        all_mistakes[question_id] = all_mistakes.get(question_id, 0) + 1

    save_mistakes(exam_type, all_mistakes)
    return {"saved": len(request.wrong_question_ids)}


# ──────────────────────────────────────────────
# AI Assistant Interface
# ──────────────────────────────────────────────

@app.post("/api/chat")
def chat_with_ai(request: ChatRequest):
    """
    Chat with AI assistant, in-depth answering of questions.
    Support multi-round conversation (pass historical messages through history field).
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured, please set in .env file")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Build system prompt
    options_text = "\n".join(request.options) if request.options else "（No options）"
    system_prompt = f"""You are a professional System Architect exam tutoring teacher, good at explaining computer system architecture related knowledge in depth and in an easy-to-understand way.

Current question information:
【Stem】{request.question_stem}
【Options】
{options_text}
【Correct Answer】{request.answer}
【Official Analysis】{request.explanation}

Please give detailed, accurate, and easy-to-understand answers based on the above question information combined with student's questions.
When explaining, you can:
1. Explain related concepts and principles in depth
2. Compare and analyze differences between options
3. Give examples of actual application scenarios
4. Supplement related test point knowledge
Please answer in Chinese, language clear and concise."""

    # Build message list
    messages = [{"role": "system", "content": system_prompt}]

    # Add historical conversations (keep up to last 10 rounds)
    for history_item in request.history[-10:]:
        role = history_item.get("role", "user")
        content = history_item.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Add current user message
    messages.append({"role": "user", "content": request.user_message})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=1500,
        )
        ai_reply = response.choices[0].message.content
        return {"reply": ai_reply}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"AI service call failed: {str(error)}")


# ──────────────────────────────────────────────
# Frontend Page Entry
# ──────────────────────────────────────────────

@app.get("/")
def serve_index():
    """Return frontend page"""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend page not found, please confirm static/index.html exists")
    return FileResponse(index_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)