---
name: xilinx-jtag-debug
description: "Use when performing authorized Xilinx/AMD FPGA board bring-up or hardware debugging through Vivado Hardware Manager, JTAG/hw_server, bitstream programming, or ILA capture and analysis, including U230. 用于实际 FPGA 上板下载、ILA 抓取与故障定位；不因普通可综合 RTL 编写、仿真、纯代码审查或只讨论 JTAG 概念而自动操作硬件。"
---

# Xilinx JTAG 与 ILA 调试

从实际 U230 调试流程提炼的可复用上板方法。用 Vivado 批处理完成连接、下载和 ILA 导出，再结合项目状态与波形证据定位问题；默认无需用户手动打开 GUI 下载 bit 或观察 ILA。先读 [references/workflow.md](references/workflow.md)，U230/PCIe 项目再读 [references/u230.md](references/u230.md)。

## 范围与授权

- 当前任务或既有对话已授权的板卡调试步骤可连续执行，不逐次要求用户批准普通下载、抓取或复测。创建/安装本 skill、编写 RTL 或检查脚本本身不授权实际连接、下载或抓取。
- 先确认板卡归属和当前使用者。另一个聊天/进程正在调试同一板卡时，仅做离线分析；没有协调授权，不抢占 cable、ILA 或重启/杀掉 `hw_server`。多块板、多器件必须用准确身份选择。
- JTAG 下载是易失配置；flash 烧写、eFUSE、加密密钥、安全熔丝、批量设备复位不在默认流程内。超出当前授权范围时才就具体操作询问。
- 优先复用项目已经验证的脚本、驱动和恢复流程；不将 U230 的器件、JTAG 频率、BDF、寄存器、RF 初始化或性能基线推广到其他板卡。脚本中不固化密码、令牌或无关机器路径。

## 实施流程

1. **建立基线**：读取项目约定、近期调试记录、构建结果。确定目标板卡/器件、Vivado 与 hw_server 版本/路径、当前镜像、连接与驱动、运行中的 DMA/RF 业务、恢复镜像及可执行验证。
2. **核对产物**：记录 bit、LTX、必要时 DCP/mask 的来源、SHA-256、源版本与构建标识。bit/LTX 必须来自相同实现；文件同名或哈希被记录不证明二者配对。不能拿当前磁盘 bit 推断板上运行的镜像。
3. **执行最小实验**：先检测连接，再按任务选择下载/配置验证/抓取。每次围绕一个可检验假设改变因素，运行有限且可结束的刺激。已有足够证据时不反复重下 bit。涉及重配的项目先按其流程停止业务并准备恢复。
4. **捕获证据**：确认 ILA 时钟/复位、核身份和探针映射；在同一个活跃 Hardware Manager 会话中布防、启动刺激、等待 FULL、上传导出。布防哨兵只表示已执行 arm 命令；进一步核对真实状态与刺激时序。未 FULL 的数据不能报告成成功抓取。
5. **分析与验证**：解析 CSV 的真实表头、radix、MAP、位宽/符号；按照实际采样时钟检查握手、复位、背压、计数变化和错误。跨 ILA/时钟的样本序号不能当成同步时间。由证据区分 JTAG、镜像/配对、时钟/复位、PCIe/软件与业务逻辑问题。
6. **收尾**：失败时在已授权范围内恢复已验证基线，并重新验证控制通路/驱动/必要业务。恢复成功不是候选镜像通过。证据目录保留日志、配置、哈希、probe map、CSV/ILA、阶段结果和最终板卡状态；不能宣称未运行的项目通过。

如果本次需要修改可综合 RTL，同时应用 `fpga-rtl-standards`；仅进行 JTAG/ILA 操作不触发 RTL 编写流程。

## 可复用工具

`scripts/hw_debug.py` 仅用 Python 标准库，配套 `scripts/hw_session.tcl`；支持 `inspect` / `program` / `capture`。每次使用一个全新的证据目录：

```bash
python3 /ABS/SKILL/scripts/hw_debug.py --config session.json --out work/debug-001
python3 /ABS/SKILL/scripts/hw_debug.py --config session.json --out work/debug-002 --execute
```

第一条只校验配置并生成 Tcl，完全不访问硬件；第二条才执行 Vivado。`--execute` 是技术开关，不构成新的用户审批流程；仅在当前任务已授权且目标可用时使用。

- 从 [assets/inspect.json](assets/inspect.json) 开始，在授权范围内发现 target，随后填准确 target/device 再发现器件与 ILA。
- `program` 必须给准确 target/device/part 和 bit；程序只确认下载 API 完成，不做 flash、不自动宣称配置回读/应用健康通过。
- `capture` 必须给准确 target/device/part/ILA CELL_NAME 及匹配 LTX；模式为 `immediate` 或有明确探针比较条件的 `trigger`。参考 [assets/capture.example.json](assets/capture.example.json)，依据项目自动生成实际配置，不让用户重复手填已知信息。
- 用工作目录中的 JSON 配置承载探针/路径；脚本用编码处理 Tcl 参数，支持带空格或括号的路径。bit/LTX 路径采用绝对路径。
- 需要外部刺激时，保持 capture 进程活跃，等新目录里的 `armed.txt` 与真实状态就绪后，在另一进程运行项目有限刺激。脚本超时以秒计；整体进程也有时限。失败后核对板卡，不能把超时解释为触发事件从未发生。
- 工具范围、配置和故障判断见 workflow.md；没有硬件时只做准备/离线测试，并明确没有实板验证。

## 交付

先给出定位结论与证据强度，随后简述：使用的镜像和目标、通过/失败/未执行的阶段、关键波形或寄存器证据、恢复与最终板卡状态、仍需验证的问题。只附与本次结论直接相关的日志或图，不把“program 成功”“ILA FULL”或恢复后的测试替代候选镜像的功能验收。
