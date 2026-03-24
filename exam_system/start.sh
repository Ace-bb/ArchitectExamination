#!/bin/bash
# 系统架构师模拟做题系统 - 启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 .env 文件
if [ ! -f ".env" ]; then
  echo "⚠️  未找到 .env 文件，正在从 .env.example 复制..."
  cp .env.example .env
  echo "✅ 已创建 .env 文件，请编辑并填入你的 OPENAI_API_KEY"
  echo ""
fi

# 检查 Python 虚拟环境
if [ ! -d "venv" ]; then
  echo "📦 正在创建 Python 虚拟环境..."
  python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 正在安装依赖..."
pip install -r requirements.txt -q

echo ""
echo "🚀 启动系统架构师模拟做题系统..."
echo "📖 访问地址：http://localhost:8000"
echo "📚 题库目录：$(python3 -c "import os; print(os.path.abspath('../exam_questions'))")"
echo ""

# 启动 FastAPI 服务
python3 main.py
