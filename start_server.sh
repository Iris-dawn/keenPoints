#!/bin/bash

# KeenPoint 服务启动脚本

echo "================================"
echo "  KeenPoint 服务启动"
echo "================================"
echo ""

# 检查依赖
echo "检查依赖..."
if ! command -v uvicorn &> /dev/null; then
    echo "❌ 未找到 uvicorn，请先安装依赖："
    echo "   pip install -r requirements.txt"
    exit 1
fi

# 创建必要目录
echo "创建必要目录..."
mkdir -p logs/prompts uploads outputs downloads static

# 启动服务
echo ""
echo "🚀 启动服务..."
echo ""
echo "服务地址:"
echo "  - API:    http://localhost:8000/api"
echo "  - Prompt: http://localhost:8000/static/prompts.html"
echo "  - Docs:   http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo "================================"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
