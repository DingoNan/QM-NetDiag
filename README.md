# 网络自检工具（NetDiag）

面向一线用户的"傻瓜式"网络体检工具：双击打开 → 点一下"开始体检" → 自动跑完测试 → 一键导出报告发给运维。

**适用场景**：一体化系统连接不稳定 / 断连 / 访问缓慢时的自助排障。

---

## 一、功能一览

| 功能 | 说明 |
|---|---|
| 快速检测 | 一键完成 Ping + TCP 端口 + iperf3 三档带宽 + 路由追踪 + DNS/HTTP + 出口检测，自动生成报告 |
| 高级探测 | 自定义目标、Ping 次数、iperf3 时长/流数/反向，或单跑某项（仅 Ping/仅端口/仅带宽/仅路由） |
| 并行加速 | iperf3 三档与路由追踪并行执行，整体检测耗时压缩 50%+ |
| 历史基线 | 报告自动与同类型上次检测对比（带宽/延迟/丢包变化百分比） |
| 出口检测 | 公网目标连通性探测，辅助区分内网/出口问题（政务网隔离公网时可关闭） |
| 定时检测 | 设定时间自动跑快速检测并保存报告，异常可留痕 |
| 多网卡选择 | 本机多网卡时可指定测试源 IP（Ping/TCP/iperf3 均生效） |
| TLS 证书 | HTTPS 探测自动显示证书有效期，自签名证书同样可读 |
| 长期监测 | 周期性 Ping + TCP + HTTP 探测，记录延迟/耗时趋势，自动捕获"时断时续"不稳定事件并生成趋势图+时间线 |
| 分层诊断 | 报告自动定位问题层级：DNS 配置 / 本地网络 / 目标服务端 / 带宽限制 |
| 修复提示 | 每项异常附"下一步怎么做"（💡 建议），不懂网络也能操作 |
| 带宽自动评估 | 无需预设参考值，实测自动给出带宽估算与通俗等级说明 |
| 报告输出 | HTML 报告（含 SVG 趋势图，可打印 PDF）+ TXT 日志 + 微信一行摘要（一键复制） |
| 多目标检测 | 首页"检测连接"同时探测：映射端口 / iperf3 服务器 / 一体化系统 HTTP |
| 多平台 | Windows 32/64、银河麒麟 x64/ARM、macOS Intel/Apple 共 6 个绿色包 |
| 系统自检 | 启动自动识别系统/架构；检测上次异常退出的残留进程 |
| 图标与署名 | 政务蓝信号图标（exe/窗口/界面），报告页脚"设计：浅木·先生" |

**报告类型**：快速检测 / 高级探测 / 长期监测，历史报告页按类型分类查看。

## 二、快速开始（源码运行）

```bash
# Windows / Linux / macOS（需 Python 3.8+，麒麟需先装 python3-tkinter）
python src/main.py            # 启动图形界面
python src/main.py --selfcheck  # 仅打印系统识别信息
```

## 三、打包（生成绿色免安装包）

| 平台 | 命令 | 说明 |
|---|---|---|
| Windows | `build_win.bat` | 在 64 位 Python 环境打 Win64 包；32 位 Python 环境打 Win32 包 |
| 麒麟 x64/ARM | `bash build_kylin.sh` | 需在对应架构机器上执行（PyInstaller 不跨架构） |
| macOS | `bash build_macos.sh` | 需在对应架构 Mac 上执行 |

打包产物位于 `dist/`，含：主程序 + `tools/`（iperf3 二进制）+ `config.ini`。
分发时整体拷贝该目录即可，免安装。

## 四、目录结构

```
网络测试工具/
├── src/                    # Python 源码
│   ├── main.py             # 入口
│   ├── config.py           # 配置读写
│   ├── platform_info.py    # 系统/架构识别
│   ├── core/               # 测试引擎（ping/tcp/iperf3/tracert/dns/http）
│   ├── monitor/            # 长时监测
│   ├── report/             # HTML/TXT 报告
│   └── ui/                 # tkinter 界面
├── tools/                  # 各平台 iperf3（win32/win64 已就位，麒麟/macOS 见下）
├── docs/prototype/         # HTML 高保真界面原型（浏览器打开 index.html）
├── config.ini              # 默认配置
├── 设计文档.md              # 完整设计文档
├── build_win.bat / build_kylin.sh / build_macos.sh
└── dist/                   # 打包产物
```

## 五、iperf3 工具准备（麒麟 / macOS）
- **Windows**：`tools/win32`、`tools/win64` 已内置（注意 iperf3.exe 必须与 cygwin1.dll 同目录）
- **麒麟**：用源码包 `iperf-3.14.tar.gz` 现场编译：
  ```bash
  tar -zxf iperf-3.14.tar.gz && cd iperf-3.14
  ./configure --disable-shared && make -j$(nproc)
  cp src/iperf3 ../tools/kylin_x64/     # 或 kylin_arm64（按架构）
  ```
- **macOS**：`brew install iperf3` 后 `cp $(which iperf3) tools/macos_x64/`（Apple 芯片放 macos_arm64）

## 六、常见问题

1. **杀毒软件拦截**：PyInstaller 打包的程序可能被 360/火绒提示 → 请添加信任/白名单；本工具纯本地运行，不上传任何数据
2. **macOS 首次运行打不开**：Gatekeeper 限制 → 右键程序 →"打开"；或执行 `xattr -d com.apple.quarantine <程序路径>`
3. **麒麟提示缺少 tkinter**：`yum install -y python3-tkinter`
4. **测试报"iperf3 失败"**：确认目标服务器已运行 `iperf3 -s`，且 NAT 映射端口正确；iperf3 服务器地址可在设置中单独配置
5. **HTTPS 提示证书错误**：工具已默认忽略证书校验（自签名证书可用），如仍失败检查端口/防火墙
6. **长期监测提前结束**：若状态显示"监测异常终止"，多为目标探测异常，可重新启动；正常情况会跑满设定时长自动停止
7. **报告中文乱码**：报告统一 UTF-8，请用浏览器/记事本 UTF-8 打开

## 七、运维维护指南

- 服务器地址变更：修改 `config.ini` 中 `[目标]` 段（含 iperf3 服务器地址/端口、出口检测地址），重新分发
- 出口检测：政务网如隔离公网，将 `出口检测地址` 留空关闭，避免误报
- 定时检测：`config.ini` 的 `[定时检测]` 段或设置页配置，到点自动跑快速检测
- 参考带宽：留空即自动评估；如已知线路带宽可填写，用于参考对比
- 收集用户报告：按"机器名+日期"归档，可沉淀为网络质量台账
- 建议用户自测流程：快速检测 → 有异常则开 10 分钟长期监测（含趋势图）→ 报告发给运维
