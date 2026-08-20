# -*- coding: utf-8 -*-
"""
网络自检工具 入口
用法：
  python src/main.py            # 图形界面（推荐）
  python src/main.py --selfcheck  # 仅系统自检，不启动界面
"""
import argparse
import sys
import os

# 兼容源码直接运行（将 src 加入模块搜索路径）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="网络自检工具")
    parser.add_argument("--selfcheck", action="store_true", help="仅打印系统自检信息")
    args = parser.parse_args()

    from platform_info import get_system_info

    info = get_system_info()
    if args.selfcheck:
        import json
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return

    # 图形界面（无显示环境时给出提示；异常写入日志文件便于排障）
    try:
        from ui import MainWindow
    except Exception as exc:  # noqa: BLE001
        import traceback
        msg = f"无法启动图形界面：{exc}\n{traceback.format_exc()}"
        print(msg)
        try:
            if getattr(sys, "frozen", False):
                log_path = os.path.join(os.path.dirname(sys.executable), "nettest_error.log")
            else:
                log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        "nettest_error.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(msg)
            print(f"错误详情已写入：{log_path}")
        except OSError:
            pass
        sys.exit(1)

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
