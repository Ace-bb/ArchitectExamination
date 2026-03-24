# ￼ 系统架构师备考系统

基于 FastAPI + Vue 3 + Element Plus 构建的系统架构师考试模拟练习平台，支持章节浏览、答题批改、错题本记录和 AI 深度解析。

---

## 功能特性

- **￼ 章节导航**：左侧树形菜单，按章节/子章节分层展示全部 21 套题库，点击子章节即可加载题目
- **￼ 交互答题**：点击选项选择答案，支持查看/隐藏答案解析
- **￼ 提交批改**：完成作答后一键提交，系统自动批改并高亮正确/错误选项，展示得分率汇总
- **￼ 错题本**：每次提交后自动将错题（含未作答）累计记录到本地，下次打开同一章节时显示历史错误次数
- **￼ AI 助手**：右侧对话面板，选择任意题目向 GPT-3.5-turbo 提问，支持多轮对话深度解析考点

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
```markdown
## 一、子章节标题

**题目1：** 题干内容
A. 选项A
B. 选项B
**正确答案：** A
**解析：** 解析内容

---
```

**格式二**（如 `030_21_exam.md`）：
```markdown
## 一、子章节标题

### 题目1：题干内容
A. 选项A
B. 选项B
**正确答案：A**
**解析：** 解析内容

---
```

---

## 启动方式

### 方式一：一键启动脚本（推荐）

```bash
bash exam_system/start.sh
```

脚本会自动完成：创建虚拟环境 → 安装依赖 → 启动服务。

### 方式二：手动启动

```bash
cd exam_system

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动后端服务
python3 main.py
```

服务启动后访问：**http://localhost:8000**

### 前端访问

前端为单页 HTML 文件，由后端直接托管，**无需单独启动**。

如需使用 VS Code Live Server 等工具单独打开 `static/index.html`，请确保 `index.html` 中的 `API_BASE_URL` 指向正确的后端地址（默认已配置为 `http://127.0.0.1:8000`）。

---

## 使用流程

1. 启动后端服务，浏览器访问 `http://localhost:8000`
2. 在左侧菜单点击章节名称展开子章节列表
3. 点击子章节加载该节题目
4. 点击选项选择答案，可随时点击「查看答案」查看解析
5. 完成作答后点击底部「￼ 提交批改」按钮
6. 查看批改结果：正确选项绿色高亮，错误选项红色高亮，底部显示得分率
7. 点击题目卡片上的「向AI提问」，在右侧对话框向 AI 助手提问
8. 下次打开同一子章节时，历史做错的题目旁会显示 `￼ 错过 N 次`

---

## 注意事项

- 错题本数据保存在 `exam_system/mistakes.json`，该文件自动生成，请勿手动删除
- AI 功能需要有效的 `OPENAI_API_KEY`，未配置时 AI 对话接口会返回错误提示
- 题库目录路径可通过 `.env` 中的 `EXAM_QUESTIONS_DIR` 自定义