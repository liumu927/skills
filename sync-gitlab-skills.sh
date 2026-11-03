#!/bin/sh
# 把指定的 skill 以「子目录」形式同步到内网 GitLab 的 skills 项目。
#
# 设计要点：
#   - 源仓库（E:\project\skills）仍是唯一真源，本脚本只产出“发布视图”的提交；
#   - 不改工作区、不建临时分支、不碰 .git 索引（用独立索引文件）；
#   - 每次的父提交 = GitLab 当前 main，所以是**快进推送**，不需要 force、能过保护分支；
#   - 以后要加第二个 skill：sh sync-gitlab-skills.sh dingtalk-integration other-skill
#
# 用法：
#   sh sync-gitlab-skills.sh                        # 默认只同步 dingtalk-integration
#   sh sync-gitlab-skills.sh dingtalk-integration code-dojo
#   WRAPPER=skills sh sync-gitlab-skills.sh         # 需要多一层 skills/ 时（布局变成 skills/<name>/）
#   GITLAB_REMOTE=gitlab GITLAB_BRANCH=main sh sync-gitlab-skills.sh
set -e

REMOTE="${GITLAB_REMOTE:-gitlab}"
BRANCH="${GITLAB_BRANCH:-main}"
WRAPPER="${WRAPPER:-}"                  # 留空 = 根目录下 <skill>/；设为 skills = skills/<skill>/
SKILLS="${*:-dingtalk-integration}"

cd "$(git rev-parse --show-toplevel)"

# 用独立索引文件，绝不动到主索引/工作区
IDX=".git/tmp-sync-index.$$"
rm -f "$IDX"
export GIT_INDEX_FILE="$IDX"
trap 'rm -f "$IDX"' EXIT INT TERM

git read-tree --empty
INCLUDED=""
for s in $SKILLS; do
  src="my-skills/$s"
  if ! git cat-file -e "HEAD:$src" 2>/dev/null; then
    echo "跳过（源仓库无此目录）: $s" >&2
    continue
  fi
  if [ -n "$WRAPPER" ]; then
    prefix="$WRAPPER/$s/"
  else
    prefix="$s/"
  fi
  git read-tree --prefix="$prefix" "HEAD:$src"
  INCLUDED="$INCLUDED $s"
done

if [ -z "$INCLUDED" ]; then
  echo "没有可同步的 skill，退出" >&2
  exit 1
fi

TREE=$(git write-tree)
unset GIT_INDEX_FILE

# 取远端当前 main 作为父提交；顺手判断内容是否真的变了（避免刷无用提交）
PARENT=""
if git fetch -q "$REMOTE" "$BRANCH" 2>/dev/null; then
  PARENT=$(git rev-parse FETCH_HEAD)
  if [ "$(git rev-parse "$PARENT^{tree}")" = "$TREE" ]; then
    echo "内容无变化，跳过推送（远端已是 $(git rev-parse --short "$PARENT")）"
    exit 0
  fi
fi

MSG="sync(${WRAPPER:+$WRAPPER/}):$INCLUDED from source $(git rev-parse --short HEAD)"
if [ -n "$PARENT" ]; then
  COMMIT=$(git commit-tree "$TREE" -p "$PARENT" -m "$MSG")
else
  COMMIT=$(git commit-tree "$TREE" -m "$MSG")
fi

echo "→ 目标树顶层：$(git ls-tree --name-only "$TREE" | tr '\n' ' ')"
echo "→ 新提交：$(git rev-parse --short "$COMMIT")（父：${PARENT:-无}）"
git push "$REMOTE" "$COMMIT:refs/heads/$BRANCH"
