# FPGA skills for Codex

供多台电脑部署和维护的 Codex FPGA 技能。

| Skill | 自动匹配场景 |
|---|---|
| `fpga-rtl-standards` | 生成、修改或重构可综合 Verilog/SystemVerilog RTL |
| `xilinx-jtag-debug` | 已授权的 Xilinx/AMD 实板 JTAG 下载、Vivado Hardware Manager/ILA 调试 |

编码规范来自团队提供的文档；硬件调试技能提炼自实际 U230 SDR/PCIe 下载、抓取、验证和恢复流程。安装或加载 skill 本身不会连接板卡、下载 bit 或运行 RF/DMA。

## RTL 编码技能触发范围

**只在生成、修改或重构可综合的 Verilog/SystemVerilog RTL 时自动匹配。**

- 约束团队命名、复位、输入输出寄存、data/valid 对齐、算术位宽、FSM、CDC、数组及排版。
- 单独编写 testbench、UVM、验证用 SVA、仿真脚本、软件/模型、代码讲解或独立审查不自动调用。
- 同时写 RTL 和测试时，仅约束可综合 RTL 部分。
- 已有接口、协议和延迟契约优先于团队默认结构；不为套用规范而静默增加寄存级。
- 用户仍可显式输入 `$fpga-rtl-standards`。自动匹配由 Codex 根据描述判断，不等同于强制 lint 门禁。

## 安装到其他电脑

需要 Git 和 Python 3.8 或更高版本；安装脚本只用 Python 标准库，不需要 pip 依赖。

Linux/macOS：

```bash
git clone https://github.com/black-pigeon/fpga_skills_for_codex.git
cd fpga_skills_for_codex
python3 install.py
```

Windows PowerShell：

```powershell
git clone https://github.com/black-pigeon/fpga_skills_for_codex.git
cd fpga_skills_for_codex
py -3 install.py
```

以上命令默认只安装 `fpga-rtl-standards`，保留早期用法。要安装 JTAG 调试技能，或同时安装两个：

```bash
python3 install.py --skill xilinx-jtag-debug
python3 install.py --skill fpga-rtl-standards xilinx-jtag-debug
```

Windows 使用 `py -3` 替代 `python3`。如果已安装其中一个，选择缺失的技能，或对两者都加 `--update`（会备份旧版）。

默认复制到当前用户的 `~/.agents/skills/fpga-rtl-standards/`，Windows 对应 `%USERPROFILE%\.agents\skills\fpga-rtl-standards\`。这是当前 Codex 文档列出的用户级 skills 目录。

如果目标电脑已经把同名 skill 安装在 `~/.codex/skills/`，请继续使用已有位置，避免两个目录同时保留同名副本：

```bash
python3 install.py --dest ~/.codex/skills --update
```

使用了自定义 `CODEX_HOME` 的电脑，显式把 `--dest` 指向已有的 skills 目录。本脚本不会修改 Codex 全局配置，也不会修改任何 RTL 工程。

安装后在 Codex 下一轮交互中使用；若技能列表尚未显示，重启 Codex。例如：

```text
请用 SystemVerilog 编写一个可综合的参数化乘加流水线，输入 16 位有符号数，无背压。
```

也可显式验证 skill：

```text
请使用 $fpga-rtl-standards 编写一个可综合的同步 FIFO。
```

### 直接让 Codex 从仓库安装

在另一台电脑的 Codex 中输入：

```text
请使用 skill-installer，从 black-pigeon/fpga_skills_for_codex 仓库安装 skills/fpga-rtl-standards 和 skills/xilinx-jtag-debug。
```

系统安装器支持从 GitHub 的指定子目录安装；如果已存在同名目录，应先确认更新方式，避免误覆盖本机修改。

## 更新

仓库与已安装目录是两份文件。`git pull` 只更新仓库；随后运行安装脚本才会更新已安装的 skill，不自动定时同步。

```bash
git pull --ff-only
python3 install.py --skill fpga-rtl-standards xilinx-jtag-debug --update
```

Windows 将最后一行的 `python3` 替换为 `py -3`。也可只指定需要更新的 skill。如果首次安装使用了 `--dest`，更新时使用相同参数。

首次安装不会覆盖已有同名目录。`--update` 会把原目录完整备份到安装目录的同级 `skill-backups/` 中，再安装新版本；若目标是符号链接，则停止并要求更新链接源。安装后的 `.install-source.json` 记录仓库、子目录、Git 提交（若有）和时间，方便追溯版本。

要维护技能，编辑本仓库对应的 `skills/<skill-name>/`，提交并推送；各电脑拉取、重新安装即可。直接修改安装目录不会自动回写仓库。

## JTAG/ILA 调试技能

支持发现 target/device、核对 bit/LTX 来源和哈希、Vivado 批量下载、按条件或立即抓取 ILA、等待 FULL 后导出 CSV/ILA、读取探针映射、结合项目脚本诊断并恢复基线。bit 下载成功、配置回读通过和应用功能正常分别记录。

在 Codex 中说：

```text
请使用 $xilinx-jtag-debug 排查这块 U230 的 PCIe BAR 为什么读回全 1。
先核对板卡占用、当前镜像和控制通路，再选择需要的 ILA 实验。
```

助手负责从项目和 inventory 生成配置，不需要用户反复手填已知信息。先检查其他聊天/进程是否正占用该板卡；skill 不启动第二个并行调试者，也不抢占别人的 JTAG/ILA。当前请求没有授权的下载或抓取不会因安装而发生。

通用包装脚本默认只做离线准备，`--execute` 才运行 Vivado：

```bash
python3 skills/xilinx-jtag-debug/scripts/hw_debug.py --config skills/xilinx-jtag-debug/assets/inspect.json --out work/jtag-inventory-plan
```

实际硬件调试需要可用 Vivado、线缆支持、已有 hw_server、对应板卡及准确的 bit/LTX。脚本不自动烧 flash、不操作 eFUSE、不重启别人的 server；PCIe 重枚举、驱动、AD9361/RF 与恢复由助手在已授权范围内复用项目流程。详细配置、来源与故障判断在该 skill 的 `references/`。

新工具经过离线 fake Hardware Manager 测试，未以安装为由连接 U230 做实板试验；不能把原项目的实板经验等同于新包装脚本已经实板签核。

## 仓库结构

```text
skills/fpga-rtl-standards/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── rtl-rules.md
│   ├── source-notes.md
│   └── source-extract.txt
└── assets/
    ├── dot2_pipeline.sv
    └── tb_dot2_pipeline.sv
skills/xilinx-jtag-debug/
├── SKILL.md
├── agents/openai.yaml
├── scripts/hw_debug.py
├── scripts/hw_session.tcl
├── references/
└── assets/
install.py
tests/test_install.py
tests/test_jtag_debug.py
```

原文页码、条件性采纳、工程修正及来源身份保存在 `source-notes.md`；全文文字提取仅用于溯源，不作为独立的 AI 执行指令。

## 验证

安装器和 JTAG 工具测试只写系统临时目录；使用 fake Hardware Manager，不连接板卡、不改本机已安装技能：

```bash
python3 -m unittest discover -s tests -v
```

如已安装 Icarus Verilog 与 Verilator，可在仓库根目录检查示例：

```bash
mkdir -p work
iverilog -g2012 -s tb_dot2_pipeline -o work/dot2.vvp skills/fpga-rtl-standards/assets/dot2_pipeline.sv skills/fpga-rtl-standards/assets/tb_dot2_pipeline.sv
vvp work/dot2.vvp
verilator --lint-only --top-module dot2_pipeline -Wall skills/fpga-rtl-standards/assets/dot2_pipeline.sv
```

编译、lint 和仿真不能替代器件综合、布局布线、STA、CDC 签核。安装不依赖这些硬件工具。

Codex skills 官方说明：<https://developers.openai.com/codex/skills/>
