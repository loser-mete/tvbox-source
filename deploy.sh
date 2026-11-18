#!/usr/bin/env bash
# 把当前目录推送到 GitHub 仓库（在你自己的电脑上运行，用你自己的 GitHub 账号）
# 用法：先在 GitHub 网页创建一个空的公开仓库 tvbox-source，然后运行本脚本
set -e

REPO="https://github.com/loser-mete/tvbox-source.git"

echo "==> 初始化 git"
git init
git branch -M main

echo "==> 添加远端"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPO"
else
  git remote add origin "$REPO"
fi

echo "==> 提交文件"
git add -A
git -c user.name="loser-mete" -c user.email="loser-mete@users.noreply.github.com" commit -m "init: TVBox 聚合源（自动更新+剔除失效源+直播源）" || echo "无新变更"

echo "==> 推送（如弹出浏览器登录，请完成 GitHub 授权）"
git push -u origin main --force

echo "==> 完成！源地址："
echo "https://raw.githubusercontent.com/loser-mete/tvbox-source/main/config.json"
