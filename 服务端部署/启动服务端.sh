#!/usr/bin/env bash
# ============================================================
# 网络自检工具 - 服务端 iperf3 一键启动脚本
# 用途：在服务器（麒麟 V10 / 统信等）上常驻启动 iperf3 服务端，
#       供客户端"快速体检 / 长期监测"使用。
# 用法：sudo bash 启动服务端.sh [端口]
#       默认端口 5201（与 NAT 映射 30014 -> 5201 对应）
# ============================================================
set -e

PORT="${1:-5201}"
SERVICE="iperf3-server"
UNIT_DIR="/etc/systemd/system"
UNIT_FILE="${UNIT_DIR}/${SERVICE}.service"

echo "============================================"
echo " iperf3 服务端部署 - 端口 ${PORT}"
echo "============================================"

# ---------- 0. 定位 iperf3 ----------
IPERF3="$(command -v iperf3 2>/dev/null || true)"
if [ -z "$IPERF3" ]; then
    for p in /usr/local/bin/iperf3 /usr/bin/iperf3 /opt/iperf-3.14/src/iperf3; do
        [ -x "$p" ] && IPERF3="$p" && break
    done
fi
if [ -z "$IPERF3" ] || [ ! -x "$IPERF3" ]; then
    echo "[错误] 未找到 iperf3 可执行文件。"
    echo "       请先按工具包《服务端部署说明.md》编译 iperf3，"
    echo "       或修改本脚本第 15 行附近的 IPERF3 路径。"
    exit 1
fi
echo "[1/4] 使用 iperf3: ${IPERF3}"

# ---------- 1. 写入 systemd 服务 ----------
if [ "$(id -u)" -ne 0 ]; then
    echo "[错误] 请用 root 或 sudo 执行本脚本。"
    exit 1
fi
echo "[2/4] 写入 systemd 服务: ${UNIT_FILE}"
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=iperf3 network test server (NetDiag)
After=network.target

[Service]
Type=simple
ExecStart=${IPERF3} -s -p ${PORT}
Restart=always
RestartSec=5
StandardOutput=append:/var/log/iperf3_server.log
StandardError=append:/var/log/iperf3_server.log

[Install]
WantedBy=multi-user.target
EOF

# ---------- 2. 启动并设为开机自启 ----------
echo "[3/4] 启动服务并设置开机自启..."
systemctl daemon-reload
systemctl enable --now "$SERVICE"
sleep 1

# ---------- 3. 验证 ----------
if systemctl is-active --quiet "$SERVICE"; then
    echo "[4/4] 服务运行中 ✅"
else
    echo "[4/4] 服务启动失败 ❌，查看日志: journalctl -u ${SERVICE} -n 50"
    exit 1
fi
echo ""
echo "监听验证:"
ss -tlnp | grep ":$PORT" || echo "  (未检测到监听，请检查端口占用)"
echo ""
echo "============================================"
echo " 部署完成！关键信息："
echo "   服务名: ${SERVICE}"
echo "   监听:   :${PORT}  (内网)"
echo "   映射:   NAT 网关需将 外网 30014 -> 内网 ${PORT}"
echo "   客户端: config.ini 中 外网映射地址/端口 需与此对应"
echo "   日志:   journalctl -u ${SERVICE} -f"
echo "============================================"
