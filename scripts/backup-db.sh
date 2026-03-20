#!/bin/bash
set -e

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/agent_db_${DATE}.sql"

mkdir -p ${BACKUP_DIR}

echo "🗄️  开始数据库备份..."

# 从环境变量读取
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-agent_db}"
PGUSER="${PGUSER:-postgres}"

# 执行备份
pg_dump -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE} \
    --format=plain \
    --no-owner \
    --no-acl \
    > ${BACKUP_FILE}

# 压缩
gzip ${BACKUP_FILE}
BACKUP_FILE="${BACKUP_FILE}.gz"

echo "✅ 备份完成: ${BACKUP_FILE}"

# 清理旧备份 (保留最近 30 天)
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +30 -delete

# 上传到 S3 (可选)
if [ -n "${S3_BUCKET}" ]; then
    aws s3 cp ${BACKUP_FILE} s3://${S3_BUCKET}/backups/
    echo "☁️  已上传到 S3"
fi
