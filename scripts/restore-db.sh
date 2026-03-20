#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE=$1

echo "🔄 开始恢复数据库..."

# 解压
if [[ $BACKUP_FILE == *.gz ]]; then
    gunzip -c ${BACKUP_FILE} > /tmp/restore.sql
    RESTORE_FILE="/tmp/restore.sql"
else
    RESTORE_FILE=${BACKUP_FILE}
fi

# 确认
echo "⚠️  这将覆盖当前数据库!"
read -p "确认继续? (yes/no): " confirm

if [ "${confirm}" != "yes" ]; then
    echo "❌ 已取消"
    exit 1
fi

# 执行恢复
psql -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE} < ${RESTORE_FILE}

echo "✅ 恢复完成"

# 清理
rm -f /tmp/restore.sql
