#!/usr/bin/env bash
# ============================================================
# NetDiag - macOS 打包脚本（PyInstaller onedir）
# 必须在对应架构的 Mac 上执行：
#   Intel Mac -> macos_x64 包；Apple Silicon Mac -> macos_arm64 包
# 首次运行请先处理 Gatekeeper：xattr -d com.apple.quarantine
# ============================================================
set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

echo "=== NetDiag macOS Build ==="

command -v python3 >/dev/null 2>&1 || { echo "错误: 未找到 python3（请安装 Python 3.8+）"; exit 1; }

python3 -m PyInstaller --version >/dev/null 2>&1 || {
  echo "安装 PyInstaller..."
  pip3 install pyinstaller
}

# 架构识别
ARCH=$(uname -m)
case "$ARCH" in
  x86_64) SUB=macos_x64 ;;
  arm64)  SUB=macos_arm64 ;;
  *) echo "不支持的架构: $ARCH"; exit 1 ;;
esac
echo "检测到架构: $ARCH -> 工具目录 tools/$SUB"

# iperf3 工具检查
if [ ! -f "tools/$SUB/iperf3" ]; then
  echo "注意: tools/$SUB/iperf3 不存在"
  echo "请先安装并复制: brew install iperf3 && cp \$(which iperf3) tools/$SUB/"
  exit 1
fi

# 打包
PKG_NAME="NetDiag_${SUB}"
python3 -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name "$PKG_NAME" \
  --paths src \
  src/main.py

# 组装
DIST="dist/$PKG_NAME"
cp -r tools "$DIST/tools"
cp config.ini "$DIST/"
cp README.md "$DIST/使用说明.md"

echo ""
echo "=== 打包完成 ==="
echo "输出目录: $DIST"
echo "分发后如遇 Gatekeeper 拦截：右键 -> 打开，或 xattr -d com.apple.quarantine <程序>"
