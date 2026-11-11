# 操作、配置与证据

## 环境与设备归属

查项目脚本、进程和运行记录，定位 Vivado 可执行文件及已有 hw_server 地址；工具版本以本机实际安装和目标工程为准。不要为检查工具版本自动启动新的 hw_server，不杀其他进程、不抢其他会话的 ILA。此 skill 的本机离线测试不会访问板卡。

先做 inventory；多个 target 不选第一项，多个同型号器件不只按 PART 选择。target/device 使用工具返回的完整 NAME；part 使用器件属性的精确值，ILA 使用完整 CELL_NAME。不同机器的 USB/JTAG 序列号不同，不从示例复制旧地址。

优先用普通桌面用户运行 Vivado，复用已配置的线缆支持和访问权限。PCIe remove/rescan、驱动操作如确实需要提升权限，限定到项目工具；不把 sudo 密码写进 skill/脚本。共享库环境冲突以实际错误定位，必要时只清理 Vivado 进程继承的特定变量，不改全局环境。

## 配置接口

通用键：

| 字段 | 含义 |
|---|---|
| `action` | `inspect` / `program` / `capture` |
| `server` | 已有 hw_server，如 `localhost:3121` |
| `vivado` | 可执行路径，省略时从 PATH 查找 |
| `target` | 精确 cable target NAME；inspect 留空时仅列出 targets，不打开任意 cable |
| `device` | 精确器件 NAME；inspect 指定 target 且省略 device 时仅列器件 |
| `part` | 精确预期 PART；program/capture 必填，工具核对属性 |
| `jtag_hz` | 可选的显式 cable 时钟设置，不默认强加 6 MHz |
| `timeout_seconds` | ILA FULL 轮询超时，单位秒，默认 10；正数且最多 3600 |
| `process_timeout_seconds` | Vivado 进程上限，默认 `max(180, timeout_seconds+60)`；必须大于抓取超时 |
| `bit` / `ltx` | 已核对的绝对产物路径；分别用于 program/capture |
| `bit_sha256` / `ltx_sha256` | 可选的预期哈希；给出时在运行前严格核对 |
| `ila` | capture 的精确 ILA CELL_NAME |
| `mode` | `immediate` 或 `trigger`；trigger 模式要求明确的比较条件 |
| `probes` | 可选 `{"探针完整NAME": 期望位宽}`，用于发现 LTX/定义漂移 |
| `triggers` | `{"探针完整NAME": "eq1'b1"}` 等 eq/ne 二进制/十六进制比较；按实际 WIDTH 核对 |
| `trigger_position` | 触发位置，默认 0；按 ILA 实际采样深度设置，非法值由 Vivado 拒绝 |

不支持的键直接报错，避免拼写错误被默默忽略。所有期望哈希只是输入身份检查，不能证明镜像与 LTX 的语义配对，也不能证明板上运行身份。

program 例子（由助手替换准确身份与路径）：

```json
{
  "action": "program",
  "server": "localhost:3121",
  "target": "inventory 中的完整 target NAME",
  "device": "inventory 中的精确 device NAME",
  "part": "xc7a200t",
  "bit": "/absolute/path/to/confirmed/design.bit"
}
```

检查 LTX 配对后再 capture。辅助脚本不自动启动测试程序、读写 BAR、重新枚举 PCIe、烧写 flash，也不替用户选择/执行恢复镜像；这些步骤必须由当前助手复用项目流程协调。

## 捕获中的关键约束

- `refresh_hw_device` 使用匹配的 PROBES.FILE/FULL_PROBES.FILE 后，确认 ILA 名字与探针名、WIDTH、MAP。不绕过 UUID mismatch 或 debug hub clock 错误。
- 清除该 ILA 上支持触发的探针比较条件，再设本次条件；基础工具用 `reset_hw_ila` 清理残留控制/比较条件，再采用 `CONTROL.TRIGGER_MODE BASIC_ONLY`、`CONTROL.CAPTURE_MODE ALWAYS`、AND trigger。复杂 OR、advanced trigger、窗口/存储资格等使用项目专用脚本，不能把本工具当成等价替代。
- 采样时钟必须存在。DMA/业务刺激前先布防，capture 进程不退出；若先退出再开另一批处理，会丢失本次会话上下文，不能假定新会话能继续旧 capture。
- `armed.txt` 不是 FULL 证明，也不保证真实 ARMED 属性已更新；必要时脚本扩展/项目脚本查询真实状态后再刺激。对极短刺激，优先使用项目已验证的单会话握手方案。
- Vivado 的状态通知存在异步缓存；轮询中先 `update`，再读 `STATUS.CORE_STATUS`，并有固定毫秒截止时间。
- `wait_on_hw_ila -timeout` 单位为**分钟**。历史脚本的 `0.05` 是 3 秒，`90` 会是 90 分钟。新工具直接按秒转毫秒轮询，不能把原脚本中的 90 复制为“90 秒”。
- 正常路径只在 FULL 时 `upload_hw_ila_data`，然后导出非空 `.csv` 和 `.ila`；错误清理时按 UG835 用 upload 停止本次未完成采集，丢弃返回对象，不导出或算作成功。进程 timeout、丢线、IDLE/ARMED/POST_TRIGGER 等状态都不作为有效完成；不拿以前的 CSV 填补本次证据。
- 每次使用新目录；保存 `probe-map.tsv`，解析 CSV 时识别 Sample in Buffer、Sample in Window、Trigger、radix 行以及真实信号列。对 X/Z/空值显式标未知，不把它们转成零。
- 先用 MAP 重建向量，再按总位宽做符号扩展/截取。单核同一时钟的并行探针可比较同拍事件；多个 ILA/时钟域需要明确同步基准。抓取中的连续样本计数不等于业务吞吐率，除非采样使能/时钟和存储资格已确认。

## 结论分级

阶段分别记录：连接成功、下载 API 成功、配置回读通过、镜像 ID 确认、ILA FULL、控制通路通过、DMA/协议通过、RF/业务通过、恢复完成。

- program_hw_devices 成功不代表 verify_hw_devices 通过；bit 文件哈希也不是板上读回校验。
- 配置回读需匹配的 DCP/bit、mask 和器件可读性；BRAM/动态资源/禁止回读等会影响结论。不能用任意 mask 忽略差异，也不能把一次 verify 失败直接判定器件坏。
- 配置回读对照实验依具体器件和 Vivado 版本，默认不包含在通用下载脚本；使用项目已验证的 create_hw_bitstream/verify_hw_devices/readback 流程并保留原始结果。
- 触发未完成可以由条件不成立、窗口不覆盖、时钟停、复位、错 LTX、无刺激或连接问题导致。按证据逐个排除，不等于已经证明业务事件不存在。
- JTAG 访问、ILA 配置和正常抓取也可能改变调试环境/资源开销；新增 ILA 或 post-route ECO 需重新记录实现来源、时序与功能基线，不当成无侵入的纯观察。

## 官方依据

核对日期 2026-11-11；API 核对使用与来源工程一致的 2022.2 文档，运行时使用目标机器对应版本的文档。以下是 API/行为依据，不是新脚本在所有版本/器件上的实测声明：

- AMD UG908 Programming and Debugging，Tcl Commands for ILA Core and hw_ila_data Objects：`https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Tcl-Commands-for-ILA-Core-and-hw_ila_data-Objects`
- AMD UG835 wait_on_hw_ila，2022.2，timeout 单位分钟：`https://docs.amd.com/r/2022.2-English/ug835-vivado-tcl-commands/wait_on_hw_ila`
- AMD UG835 write_hw_ila_data，2022.2，CSV/原生数据导出：`https://docs.amd.com/r/2022.2-English/ug835-vivado-tcl-commands/write_hw_ila_data`
- AMD UG835 reset_hw_ila / run_hw_ila，2022.2，重置控制/比较、BASIC_ONLY 与 ALWAYS：`https://docs.amd.com/r/2022.2-English/ug835-vivado-tcl-commands/reset_hw_ila`、`https://docs.amd.com/r/2022.2-English/ug835-vivado-tcl-commands/run_hw_ila`
- AMD UG835 upload_hw_ila_data，2022.2，未 FULL 时停止当前采集的行为：`https://docs.amd.com/r/2022.2-English/ug835-vivado-tcl-commands/upload_hw_ila_data`
- AMD UG908 Specifying the Hardware Probes File，bit/LTX 的实现一致性与探针文件绑定：`https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Specifying-the-Hardware-Probes-File`

本技能可移植层经过 fake Hardware Manager/Tcl 离线测试；原 U230 实验是来源证据，不等于新包装脚本已经实板验收。不同版本的属性差异应通过具体错误和 `list_property/report_property` 定位，不能全局 catch 掩盖失败。
