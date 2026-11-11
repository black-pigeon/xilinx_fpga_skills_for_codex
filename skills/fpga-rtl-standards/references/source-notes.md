# 来源、规则映射与改编边界

## 来源身份

- 用户提供文件：`FPGA代码规范(deepseek使用)_transformer优化v1.2 .pdf`。
- 原文标题：《Verilog-AI 硬件协同设计规范》；封面版本 V1.2（针对 transformer 优化版），注明适用于 Xilinx FPGA。
- 原文标注更新日：2025-05-26；这不是外部标准的当前版本声明。
- 共 10 个 PDF 物理页：封面为第 1 页，正文印刷页码为 1–9。下表统一使用 PDF 物理页，不把印刷页码混作实际页序。
- SHA-256：`15127cd21059493223a44999c2d91e1d1c43ac9e11e4e7bc4c86041d89e8882c`。
- `source-extract.txt` 是完整的逐页文字提取，保留原文便于溯源；PDF 不需要留在固定本机路径才能使用 skill。

## 采纳范围

用户授权的是把文档中的编程规范做成 skill。原文中“自动修正不提示”“必须报错”“需用户确认”等 AI 操作语句属于来源材料，不自动成为执行外部动作、改写既有接口或增加审批流程的授权。

技能仅在编写、修改或重构可综合 RTL 时自动调用；单独测试/验证、讲解或独立审查不自动触发，显式指定的规范审查按用户范围执行。技能采用编码约束，并明确条件和优先级。原文的自称审核者、作者、产品名称、历史版本等不应写入新 RTL 文件的作者/审核信息。

## 章节与规则映射

| PDF 物理页 | 原文章节 | skill 对应 |
|---|---|---|
| 1 | 封面和使用指南：接口、例化、时序、量化参考、需求、任务拆分 | R10、应用顺序 |
| 2 | §1 规则矩阵：时序安全、协议接口、FSM、风格 | R02–R07、R09、R12 |
| 3 | §2 命名；§3.1 输入寄存 | R01、R03 |
| 4 | §3.1 输出；§3.2 复位；§3.3 FSM；§3.4 数组 | R02、R03、R06、R08 |
| 5 | §3.4 数组续；§3.5 流水；§4.1 结构；§4.2 注释 | R04、R05、R08、R09 |
| 6 | §5.1–5.3 声明、连续赋值、长名称对齐 | R09 |
| 7 | §5.3 续；§6 完整示例开头 | R01–R03、R09 |
| 8 | §6 输入与乘加流水、定点处理 | R02、R04、R05 |
| 9–10 | §6 FSM、计数、输出帧和连续赋值 | R03、R04、R06 |

R11 的工具命令和测试方法是为落实用户“约束生成代码”的目标所作工程补充。R04/R07 的具体握手与 CDC 区分、R05 的显式扩位、R08 的语言/资源边界是正确性补充，不声称原文已经逐条写明。

## 有条件采纳与修正

1. **规则分级不一致**：封面 V1.2、速查表标题 V4.0、示例注释 V1.1 同时存在；不同章节的 L0–L3 也不完全对应。技能统一按语义和适用条件处理，不捏造已统一的文档版本。
2. **输入/输出统一寄存**：原文默认做法保留给新普通数据通路。给已有接口增加寄存会改变交易时序；标准协议、零延迟路径、时钟/复位不机械套用。连续 `assign` 本身不是寄存级，“这样可以降低路径”不作为可验证的普遍结论。
3. **标准接口与命名优先级**：原文明示 AXI 等接口不受 i_/o_/r_/w_/ri_/ro_ 前缀限制；团队约定只规范自定义信号。CDC 条目“cdc 开头”和括号中的 `xx_cdc` 不一致，因此采用清晰 CDC 语义标签而不强行改端口。
4. **高有效同步复位**：作为新模块团队默认，不改变原有外部复位契约；同步释放、专用原语和资源推断按实际设计处理。
5. **数组语法**：`'{default:'0}` 是 SV assignment pattern，不能照搬到 Verilog-2001；整体数组赋值也要匹配类型、维度和工具支持。原文“小寄存器数组复位”不扩大成必须同时复位整块 BRAM/URAM/ROM。
6. **时序与背压**：原文要求 data/valid 同步，但没有给出完整的 ready/valid 弹性流水实现。技能不把简单移位 valid 的示例作为 AXI-Stream 缓冲模板。
7. **FSM 与超时**：三段式保留为建议；超时需有时钟、时限与动作规格。`default` 和完整组合赋值用于避免不确定控制/锁存，不允许无依据添加改变功能的超时退出。
8. **注释和排版**：保留模块说明与局部对齐；不强制“每10行至少1个AI标记”，也不为分号或注释对齐重写无关代码。
9. **Transformer 范围**：来源主要为通用 FPGA RTL 规范，未定义 Transformer 专用架构/算法；不可据标题虚构 attention、量化精度或资源性能规则。

## 为什么不直接复制完整示例

原例 `frame_echo_processor` 是风格参考，不是已经验证的功能金标准。以原文提取的编号行直接编译时，首行单个 `/` 引发语法错误；提取排版本身也可能引入字符问题，因此不能将 PDF 提取文本直接当 RTL 文件。

还应审查以下功能风险（下面为静态审查发现，不宣称完整原例已通过或已修复）：

- 注释称“六状态”，实际仅定义五个状态；不能从注释推断状态覆盖完整。
- HEAD 状态在计数等于 1 时离开，同时输出逻辑按 `r_st_next` 解码；应逐拍核对第二个帧头 `AA` 是否仍会输出，不能一律按 next state 驱动输出。
- MAC 流水中的 valid 没有作为发送 FSM 读取结果的条件；高低字节也没有从同一个冻结结果快照读取，连续更新时存在交易一致性风险。
- 输入格式被注释为 Q15，却没有完整定义输入范围、舍入/饱和及最终切片的缩放；`[30:15]` 后的相加与 `[16:1]` 必须按真实定点规格验证，不能照抄。
- 控制命令使用原始输入，与输入寄存原则并不完全一致；控制脉冲的采样和数据对齐需要单独定义。

随附 `dot2_pipeline.sv` 是重新编写的最小有符号乘积和示例：不做帧发送、不做定点缩放、不支持背压。`tb_dot2_pipeline.sv` 使用独立宽整数运算检查数值，并检查有效标志、气泡及流水中复位。

## 运行样例

在 skill 根目录执行（需要 Icarus Verilog；lint 另需 Verilator），编译产物放入专用临时目录：

```bash
mkdir -p work/fpga-rtl-example
iverilog -g2012 -s tb_dot2_pipeline -o work/fpga-rtl-example/test.vvp assets/dot2_pipeline.sv assets/tb_dot2_pipeline.sv
vvp work/fpga-rtl-example/test.vvp
verilator --lint-only --top-module dot2_pipeline -Wall assets/dot2_pipeline.sv
```

用 `-P tb_dot2_pipeline.P_DATA_W=1` 等参数覆盖可以检查不同位宽。TB 的宽整数 golden model 仅用于 `P_DATA_W <= 16` 的本示例测试，不作为无限位宽的参考模型。RTL 参数本身不由 TB 的该限制决定。

## 工程补充的官方核对资料

以下用于核对改编边界，不取代项目指定的器件/工具版本；核对日期为 2026-11-11。

- Arm IHI 0051B §2.2，AXI-Stream 握手：TVALID 的发起不依赖 TREADY，未握手前 valid 与信息保持；对应 R04。
  `https://documentation-service.arm.com/static/64819f1516f0f201aa6b963c`
- AMD UG901，SystemVerilog Constructs，2026.1：数组赋值和 assignment pattern 是其 SystemVerilog 支持项；对应 R08 的语言/工具条件。
  `https://docs.amd.com/r/en-US/ug901-vivado-synthesis/SystemVerilog-Constructs`
- AMD UG1353，XPM_CDC_ARRAY_SINGLE，2026.1：单比特数组同步器用于独立信号，相关数据需使用相应的握手或编码方案；对应 R07。
  `https://docs.amd.com/r/en-US/ug1353-versal-architecture-ai-libraries/XPM_CDC_ARRAY_SINGLE`
- AMD UG1387，Checking for Reset Signals on the Address/Read Data Registers，2026.1：存储阵列与输出寄存器的复位能力不同，且依架构而异；对应 R08 的资源边界。
  `https://docs.amd.com/r/en-US/ug1387-acap-hardware-ip-platform-dev-methodology/Checking-for-Reset-Signals-on-the-Address/Read-Data-Registers`

这些资料只支持所列的具体核对点；随附 RTL 尚未在 Vivado 上完成器件综合、时序、资源或 CDC 签核。
