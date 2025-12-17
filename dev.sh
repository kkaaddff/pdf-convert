#!/bin/bash

# PDF 黑白转换服务开发环境启动脚本
# 使用本地 Python 环境运行

set -e

echo "🐍 启动 PDF 黑白转换服务 - 开发模式..."

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
REQUIRED_VERSION="3.12"

if [ "$PYTHON_VERSION" != "$REQUIRED_VERSION" ]; then
    echo "⚠️  警告: 检测到 Python 版本 $PYTHON_VERSION，推荐使用 Python $REQUIRED_VERSION"
    echo "如果使用 Conda，请运行: conda activate fta-xrun-chat-bot"
    read -p "是否继续？ (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查是否在虚拟环境中
if [[ "$VIRTUAL_ENV" == "" && "$CONDA_DEFAULT_ENV" == "" ]]; then
    echo "⚠️  警告: 未检测到虚拟环境，建议使用虚拟环境"
    echo "如果使用 Conda，请运行: conda activate fta-xrun-chat-bot"
    read -p "是否继续？ (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 创建必要的目录
mkdir -p uploads outputs

# 安装依赖
echo "📦 安装 Python 依赖..."
pip install -r requirements.txt

# 启动服务
echo "🚀 启动开发服务器..."
echo "📝 服务地址: http://localhost:8000"
echo "🏥 健康检查: http://localhost:8000/health"
echo "📚 API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动 uvicorn 开发服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000