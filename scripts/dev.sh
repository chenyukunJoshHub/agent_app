#!/bin/bash
set -e

echo "🚀 启动本地开发环境..."

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    exit 1
fi

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "⚠️  未找到 .env 文件，使用默认配置"
fi

# 启动服务
docker-compose up -d postgres redis backend frontend

# 等待服务就绪
echo "⏳ 等待服务启动..."
sleep 10

# 运行数据库迁移
docker-compose exec backend alembic upgrade head

echo "✅ 开发环境启动完成！"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   PgAdmin:  http://localhost:5050 (需要 --profile tools)"
