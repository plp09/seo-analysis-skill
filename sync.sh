#!/bin/bash
# SEO Analysis Skill - 推送到 GitHub
# 用法: ./sync.sh "版本更新说明"
# 示例: ./sync.sh "修复 GEO 评分合并 bug，新增自动检测"

set -e

SKILL_DIR=~/.qclaw/skills/seo-analysis
GITHUB_USER="${GITHUB_USER:-plp09}"
REPO="seo-analysis-skill"
COMMIT_MSG="${1:-技能更新}"

cd "$SKILL_DIR"

echo "=== 同步 SEO Analysis Skill 到 GitHub ==="
echo "版本: $(date '+%Y.%m.%d')"
echo "提交信息: $COMMIT_MSG"
echo ""

# 检查 git 状态
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "[初始化] 设置 GitHub 远程仓库..."
    git remote add origin "https://github.com/${GITHUB_USER}/${REPO}.git"
fi

# 提交所有更改
git add .
git commit -m "$(date '+%Y.%m.%d') - $COMMIT_MSG"

# 推送到 GitHub
echo ""
echo "正在推送..."
git push origin main

echo ""
echo "✅ 已同步到 https://github.com/${GITHUB_USER}/${REPO}"