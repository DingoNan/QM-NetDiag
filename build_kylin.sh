#!/usr/bin/env bash
# ============================================================
# NetDiag - 麒麟 Linux 打包脚本（PyInstaller onedir）
# 必须在目标架构机器上执行（PyInstaller 不跨架构）：
#   x86_64 机器 -> kylin_x64 包；aarch64 机器 -> kylin_arm64 包
# ============================================================
set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

echo "=== NetDiag Kylin Build ==="

# 0. 检查 python3
command -v python3 >/dev/null 2>&1 || { echo "错误: 未找到 python3"; exit 1; }

# 0.1 检查 tkinter（麒麟默认可能不带）
python3 -c "import tkinter" >/dev/null 2>&1 || {
  echo "提示: 缺少 tkinter，尝试安装..."
  if command -v yum >/dev/null 2>&1; then
    sudo yum install -y python3-tkinter
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get install -y python3-tk
  fi
}

# 0.2 安装/检查 PyInstaller
python3 -m PyInstaller --version >/dev/null 2>&1 || {
  echo "安装 PyInstaller..."
  pip3 install pyinstaller
}

# 1. 识别架构
ARCH=$(uname -m)
case "$ARCH" in
  x86_64|amd64)  SUB=kylin_x64 ;;
  aarch64|arm64) SUB=kylin_arm64 ;;
  *) echo "不支持的架构: $ARCH"; exit 1 ;;
esac
echo "检测到架构: $ARCH -> 工具目录 tools/$SUB"

# 2. 检查 iperf3 工具；缺失则提示编译
if [ ! -f "tools/$SUB/iperf3" ]; then
  echo "注意: tools/$SUB/iperf3 不存在"
  echo "请用源码包编译后放入:"
  echo "  tar -zxf iperf-3.14.tar.gz && cd iperf-3.14"
  echo "  ./configure --disable-shared && make -j\$(nproc) && cp src/iperf3 ../tools/$SUB/"
  exit 1
fi

# 3. PyInstaller 打包（onedir）
PKG_NAME="NetDiag_${SUB}"
python3 -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name "$PKG_NAME" \
  --paths src \
  src/main.py

# 4. 组装绿色包
DIST="dist/$PKG_NAME"
cp -r tools "$DIST/tools"
cp config.ini "$DIST/"
cp README.md "$DIST/使用说明.md"

echo ""
echo "=== 打包完成 ==="
echo "输出目录: $DIST"
echo "分发时整体拷贝该目录即可（免安装）。"
