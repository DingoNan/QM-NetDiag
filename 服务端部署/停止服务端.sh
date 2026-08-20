#!/usr/bin/env bash
# ============================================================
# 网络自检工具 - 服务端 iperf3 停止脚本
# 用法：sudo bash 停止服务端.sh
# 停止服务并取消开机自启（如需保留自启只停服务，改第 18 行注释）
# ============================================================
set -e

SERVICE="iperf3-server"

if [ "$(id -u)" -ne 0 ]; then
    echo "[错误] 请用 root 或 sudo 执行本脚本。"
    exit 1
fi

echo "停止服务: ${SERVICE}"
systemctl stop "$SERVICE" 2>/dev/null || true
systemctl disable "$SERVICE" 2>/dev/null || true
systemctl daemon-reload

if systemctl is-active --quiet "$SERVICE"; then
    echo "服务仍在运行，请检查: journalctl -u ${SERVICE} -n 30"
    exit 1
fi
echo "✅ 服务已停止，并已取消开机自启。"
echo "端口检查（应无 5201 监听）:"
ss -tlnp | grep ":5201" || echo "  5201 已无监听"
