# ￼ 系统架构师备考系统

基于 FastAPI + Vue 3 + Element Plus 构建的系统架构师考试模拟练习平台，支持章节浏览、答题批改、错题本记录和 AI 深度解析。

---

## 功能特性

- **📚 章节导航**：左侧树形菜单，按章节/子章节分层展示全部 21 套题库，点击子章节即可加载题目
- **📝 交互答题**：点击选项选择答案，支持查看/隐藏答案解析
- **✅ 提交批改**：完成作答后一键提交，系统自动批改并高亮正确/错误选项，展示得分率汇总
- **📖 错题本**：每次提交后自动将错题（含未作答）累计记录到本地，下次打开同一章节时显示历史错误次数
- **🤖 AI 助手**：右侧对话面板，选择任意题目向 GPT-3.5-turbo 提问，支持多轮对话深度解析考点
- **⚡ 性能优化**：智能缓存机制，历年真题加载速度提升近 1000 倍，二次访问几乎瞬间加载

---

## 系统架构

```
exam_system/
├── main.py              # FastAPI 后端主程序（API 路由）
├── parser.py            # Markdown 题库解析器（支持两种题目格式）
├── mistakes.json        # 错题本数据（自动生成，JSON 格式）
├── requirements.txt     # Python 依赖
├── .env                 # 环境变量配置（需自行创建）
├── .env.example         # 环境变量模板
├── start.sh             # 一键启动脚本
└── static/
    └── index.html       # Vue 3 前端单页应用（CDN 引入）

exam_questions/          # 题库目录（Markdown 格式，共 21 套）
├── 006_1_exam.md
├── 008_2_exam.md
└── ...
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3（CDN）、Element Plus、原生 CSS |
| 后端 | Python 3.10+、FastAPI、Uvicorn |
| AI   | OpenAI GPT-3.5-turbo |
| 存储 | 本地 Markdown 文件（题库）、本地 JSON 文件（错题本） |

### 后端 API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/chapters` | 获取全部章节树（含子章节列表） |
| GET  | `/api/sections/{section_id}` | 获取子章节下的所有题目 |
| GET  | `/api/mistakes/{section_id}` | 获取子章节的历史错题次数 |
| POST | `/api/mistakes` | 保存本次做错的题目（累加计数） |
| POST | `/api/chat` | 与 AI 助手多轮对话 |

---

## 配置说明

### 1. 创建环境变量文件

```bash
cd exam_system
cp .env.example .env
```

编辑 `.env` 文件，填入以下配置：

```env
# OpenAI API Key（必填）
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# API 地址（可选，默认为 OpenAI 官方地址；如使用国内代理或自定义地址请修改）
OPENAI_BASE_URL=https://api.openai.com/v1

# 题库目录路径（可选，默认为 ../exam_questions）
EXAM_QUESTIONS_DIR=../exam_questions
```

### 2. 题库格式说明

题库文件位于 `exam_questions/` 目录，每个 `.md` 文件对应一套题，解析器支持两种格式：

**格式一**（如 `006_1_exam.md`）：
```

