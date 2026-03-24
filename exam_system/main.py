"""
系统架构师模拟做题系统 - FastAPI 后端
"""

import json
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

from parser import list_exam_files, parse_exam_file

# 错题本数据文件路径
MISTAKES_FILE = os.path.join(os.path.dirname(__file__), "mistakes.json")


def load_mistakes() -> dict:
    """从本地文件读取错题记录，格式：{ question_id: count }"""
    if not os.path.exists(MISTAKES_FILE):
        return {}
    with open(MISTAKES_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}


def save_mistakes(mistakes: dict) -> None:
    """将错题记录写入本地文件"""
    with open(MISTAKES_FILE, "w", encoding="utf-8") as file:
        json.dump(mistakes, file, ensure_ascii=False, indent=2)

load_dotenv()

app = FastAPI(title="系统架构师模拟做题系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（前端页面）
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    question_id: str
    question_stem: str
    options: list[str]
    answer: str
    explanation: str
    user_message: str
    history: list[dict] = []


# ──────────────────────────────────────────────
# 题库接口
# ──────────────────────────────────────────────

@app.get("/api/chapters")
def get_chapters():
    """获取所有章节列表（树形结构）"""
    exam_files = list_exam_files()
    chapters = []

    for exam_file in exam_files:
        file_id = exam_file["file_id"]
        parsed = parse_exam_file(file_id)
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
        })

    return {"chapters": chapters}


@app.get("/api/sections/{section_id}")
def get_section_questions(section_id: str):
    """
    获取某个子章节下的所有题目。
    section_id 格式：{file_id}_s{index}，如 006_1_exam_s1
    """
    # 从 section_id 中解析出 file_id
    # section_id 格式：006_1_exam_s1 → file_id = 006_1_exam
    parts = section_id.rsplit("_s", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="无效的 section_id 格式")

    file_id = parts[0]
    parsed = parse_exam_file(file_id)
    if not parsed:
        raise HTTPException(status_code=404, detail=f"找不到文件：{file_id}")

    target_section = None
    for section in parsed["sections"]:
        if section["section_id"] == section_id:
            target_section = section
            break

    if not target_section:
        raise HTTPException(status_code=404, detail=f"找不到子章节：{section_id}")

    return {
        "section_id": target_section["section_id"],
        "title": target_section["title"],
        "chapter_title": parsed["title"],
        "questions": target_section["questions"],
    }


# ──────────────────────────────────────────────
# 错题本接口
# ──────────────────────────────────────────────

class SaveMistakesRequest(BaseModel):
    wrong_question_ids: list[str]


@app.get("/api/mistakes/{section_id}")
def get_section_mistakes(section_id: str):
    """
    获取某个子章节下各题目的历史错误次数。
    返回：{ question_id: count, ... }（只包含有错误记录的题目）
    """
    all_mistakes = load_mistakes()
    # 过滤出属于该子章节的错题（question_id 以 section_id 开头）
    section_mistakes = {
        question_id: count
        for question_id, count in all_mistakes.items()
        if question_id.startswith(section_id)
    }
    return {"mistakes": section_mistakes}


@app.post("/api/mistakes")
def save_section_mistakes(request: SaveMistakesRequest):
    """
    保存本次做错的题目，累加错误次数到本地 mistakes.json。
    """
    if not request.wrong_question_ids:
        return {"saved": 0}

    all_mistakes = load_mistakes()
    for question_id in request.wrong_question_ids:
        all_mistakes[question_id] = all_mistakes.get(question_id, 0) + 1

    save_mistakes(all_mistakes)
    return {"saved": len(request.wrong_question_ids)}


# ──────────────────────────────────────────────
# AI 助手接口
# ──────────────────────────────────────────────

@app.post("/api/chat")
def chat_with_ai(request: ChatRequest):
    """
    与 AI 助手对话，针对某道题目进行深入解答。
    支持多轮对话（通过 history 字段传递历史消息）。
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="未配置 OPENAI_API_KEY，请在 .env 文件中设置")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    # 构建系统提示词
    options_text = "\n".join(request.options) if request.options else "（无选项）"
    system_prompt = f"""你是一位专业的系统架构师考试辅导老师，擅长深入浅出地解释计算机系统架构相关知识。

当前题目信息：
【题干】{request.question_stem}
【选项】
{options_text}
【正确答案】{request.answer}
【官方解析】{request.explanation}

请根据以上题目信息，结合学生的问题，给出详细、准确、易于理解的解答。
解答时可以：
1. 深入解释相关概念和原理
2. 对比分析各选项的区别
3. 举例说明实际应用场景
4. 补充相关的考点知识
请用中文回答，语言清晰简洁。"""

    # 构建消息列表
    messages = [{"role": "system", "content": system_prompt}]

    # 添加历史对话（最多保留最近 10 轮）
    for history_item in request.history[-10:]:
        role = history_item.get("role", "user")
        content = history_item.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # 添加当前用户消息
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
        raise HTTPException(status_code=500, detail=f"AI 服务调用失败：{str(error)}")


# ──────────────────────────────────────────────
# 前端页面入口
# ──────────────────────────────────────────────

@app.get("/")
def serve_index():
    """返回前端页面"""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="前端页面未找到，请确认 static/index.html 存在")
    return FileResponse(index_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
