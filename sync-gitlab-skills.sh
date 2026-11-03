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
#   sh sync-gitlab-skills.sh --import               # 反向：把 GitLab 上他人直接提交的改动搬回工作区
#   FORCE_OVERWRITE=1 sh sync-gitlab-skills.sh      # 明知远端有他人提交仍要覆盖
set -e

IMPORT=0
if [ "$1" = "--import" ]; then IMPORT=1; shift; fi

REMOTE="${GITLAB_REMOTE:-gitlab}"
BRANCH="${GITLAB_BRANCH:-main}"
WRAPPER="${WRAPPER:-}"                  # 留空 = 根目录下 <skill>/；设为 skills = skills/<skill>/
SKILLS="${*:-dingtalk-integration}"

cd "$(git rev-parse --show-toplevel)"

# ---------- 反向模式：把远端他人改动搬回源仓库工作区 ----------
if [ "$IMPORT" = "1" ]; then
  git fetch -q "$REMOTE" "$BRANCH" || { echo "抓取 $REMOTE/$BRANCH 失败" >&2; exit 1; }
  HEADR=$(git rev-parse FETCH_HEAD)
  BASE=$(git log --format='%H %s' "$HEADR" | awk '/ sync\(/ {print $1; exit}')
  if [ -z "$BASE" ]; then
    echo "远端没有自动发布提交（sync(...)），无法确定基线；请手工比对" >&2
    exit 1
  fi
  echo "基线（最后一次自动发布）：$(git rev-parse --short "$BASE")"
  echo "目标（远端当前）：        $(git rev-parse --short "$HEADR")"
  applied=0
  for s in $SKILLS; do
    if [ -n "$WRAPPER" ]; then prefix="$WRAPPER/$s/"; else prefix="$s/"; fi
    strip=$((1 + $(printf '%s' "$prefix" | tr -cd '/' | wc -c)))
    patch=$(git diff "$BASE" "$HEADR" -- "$prefix")
    if [ -z "$patch" ]; then
      echo "  [$s] 远端无改动"
      continue
    fi
    echo "$patch" | git apply -p"$strip" --directory="my-skills/$s" --3way \
      && { echo "  [$s] 已应用到工作区"; applied=$((applied+1)); } \
      || { echo "  [$s] 应用失败，请手工处理" >&2; exit 1; }
  done
  echo ""
  echo "共 $applied 个 skill 的改动已写入工作区（**尚未提交**）。"
  echo "请复查 git status / git diff，确认无误后自行 commit。"
  echo "提示：提交后远端 HEAD 仍是那次外来提交，所以下一个「真实改动」推送时需用一次"
  echo "      FORCE_OVERWRITE=1 sh sync-gitlab-skills.sh，之后即恢复常态。"
  exit 0
fi

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

# ---- 防覆盖检查：远端最新提交若不是本脚本生成的，说明有人直接改过 GitLab ----
# 本脚本的提交主题形如 "sync(...):... from source <sha>"；其余一律视为“外来提交”。
if [ -n "$PARENT" ] && [ "${FORCE_OVERWRITE:-0}" != "1" ]; then
  SUBJ=$(git log -1 --format='%s' "$PARENT")
  case "$SUBJ" in
    sync\(*)
      : # 本脚本产出，正常继续
      ;;
    *)
      echo "" >&2
      echo "!! 已中止：GitLab 的 $BRANCH 上有【非自动发布】的提交，直接同步会覆盖它。" >&2
      echo "   该提交：$(git rev-parse --short "$PARENT")  $SUBJ" >&2
      echo "   作者/时间：$(git log -1 --format='%an %ad' --date=short "$PARENT")" >&2
      echo "" >&2
      echo "   会被本次同步覆盖的差异（remote → 本次要推的内容）：" >&2
      git diff --stat "$PARENT" "$COMMIT" | sed 's/^/     /' >&2
      echo "" >&2
      echo "   建议做法（二选一）：" >&2
      echo "     A) 先把同事的改动搬回源仓库（推荐，不丢东西）：" >&2
      echo "          sh sync-gitlab-skills.sh --import   # 打到工作区，复查后自行 commit" >&2
      echo "        注意：导入提交后，下一次「真实改动」仍会被拦一次（远端 HEAD 还是这次外来提交），" >&2
      echo "        届时用一次 FORCE_OVERWRITE=1 推送即可，之后恢复常态。" >&2
      echo "     B) 确认他那份可以丢弃，直接覆盖：" >&2
      echo "          FORCE_OVERWRITE=1 sh sync-gitlab-skills.sh $SKILLS" >&2
      exit 2
      ;;
  esac
fi

echo "→ 目标树顶层：$(git ls-tree --name-only "$TREE" | tr '\n' ' ')"
echo "→ 新提交：$(git rev-parse --short "$COMMIT")（父：${PARENT:-无}）"
git push "$REMOTE" "$COMMIT:refs/heads/$BRANCH"
