# Ettus/UHD FIFO复用与适配参考

## 原则与范围

新增或替换 FIFO 时，默认采用 Ettus/UHD 在 N310/X4xx 中的公共 FIFO 分层及 ready/valid 用法，复用项目已引入且可追溯的实现，不为每处队列重新手写存储指针。采用前核对容量、读延迟、吞吐、复位、目标器件及接口契约。不能把“在USRP使用过”当作当前PCIe/SDR链路已验证，更不能为换FIFO顺便改业务包边界、时间戳或DMA所有权。此参考不改变主skill仅针对可综合RTL的触发边界。

FIFO不能修复上游忽略full、下游违反ready/valid、错误CDC、复位释放或未收敛时序。先区分队列实现故障与使用契约故障，再局部适配；已有深度/时延承诺不合适时允许使用已验证的现有实现或目标器件FIFO IP，并说明理由，不机械全工程替换。

## 快速定位

- 模块选型与真实容量：第 1 节。
- ready/valid、不可停顿采样源与排空：第 2–3 节。
- CDC、时间戳、共同复位：第 4 节。
- 仿真先行：第 5 节。
- Xilinx IP 的 Tcl 接入与配置：第 6 节。
- 已核对的 N310/X4xx 用法及来源记录：第 7 节。

## 1. 读取实际版本再选型

UHD不同版本可能改变内部结构。先读目标checkout中的模块和完整依赖，而不是根据名字或另一版本的接口猜测。记录revision、源文件hash、来源和许可证；复制进项目vendor目录以便独立构建，不能让构建隐式依赖开发机外部checkout。保留上游copyright/SPDX和许可证文件。自有适配层另写，不批量改第三方命名、initial、reset或布局属性。

| 需求 | 可评估实现 | 关键限制 |
| --- | --- | --- |
| 单拍/两拍弹性级、打断组合ready路径 | axi_fifo_flop / axi_fifo_flop2 | 根据实际版本核对容量/复位/是否打断ready；不要把纯wire当成FIFO |
| 小型单时钟控制头/终态队列 | axi_fifo_short | 常见版本固定32项，显式使用Xilinx SRLC32E；不是可移植到任意厂商的纯RTL |
| 大型单时钟payload队列 | axi_fifo_bram | 包含同步RAM读与预取/输出级；容量和occupied语义需阅读源码及仿真，不凭名字套旧FWFT |
| 双时钟数据/控制bundle | axi_fifo_2clk / 项目已验证异步FIFO | 核对公共reset及内部同步器、停钟、容量、IP和CDC约束；不假定支持任意单边复位，单时钟SRL不能跨域 |
| 统一尺寸选择器 | axi_fifo | SIZE各分支可能是旁路、flop、固定32项SRL或BRAM；有版本SIZE=2..5全都实例化32项short，不能只按注释假定恰为2**SIZE |

已核对版本的 `axi_fifo` 分支：`SIZE<0` 为无存储旁路，`SIZE=0` 为 1 项 flop，`SIZE=1` 为 2 项 flop2，`SIZE=2..5` 为固定 32 项 SRL，`SIZE>5` 为 BRAM。`axi_fifo_flop2` 可用来打断端到端组合路径；不要无条件在全工程追加。`axi_fifo_cascade` 的前后 flop2 会增加容量/延迟，其计数接口仅反映主 FIFO，不能直接充当端到端占用。

小队列可将物理32项SRL封装为较小逻辑容量，但必须限制输入握手并发布真实逻辑capacity。例：容量16在occupied=16时ready必须为0，不得默默多收16项；边界full+pop是否接受新push要明确定义。

## 2. 适配前写明周期契约

每个wrapper写出：时钟域/reset极性及同步性、容量（含可见head/预取级）、空写后首字何时可见、稳态吞吐、满时同时读写、almost_full预留、reset输出有效性、业务旁带和清理规则。

ready/valid只在valid&&ready时移动数据。源端valid不能依赖ready来凭空决定有无数据；stall期间valid、data和所有旁带保持。复位时可通过wrapper屏蔽输入/输出握手；复位清valid/指针/占用，不给SRL/BRAM payload加整阵列reset。未复位payload在invalid时不可被使用。

旧wr_en/rd_en接口的基本映射（示意，实际信号名称遵循项目）：

```verilog
// 此例只屏蔽同步reset期间的接口交易；full/empty由ready/valid解释。
assign fifo_i_valid = i_wr_en && !i_rst;
assign fifo_o_ready = i_rd_en && !i_rst;
assign o_full = !fifo_i_ready;
assign o_empty = !fifo_o_valid;
// 未消费时payload保持由FIFO保证，不能独立打一拍flag破坏对齐。
```

full时的write通常不接受，即使同拍read使下拍有空间；不要悄悄改成接受，除非调用方契约与测试一起更新。原满写丢弃契约不等于AXIS源端可以丢弃被反压的数据：真正AXIS生产者必须保持该word直到握手。

almost_full至少覆盖生产者看到反馈后仍可能发出的在途写入数量。阈值不能对所有FIFO固定depth-1；使用的是精确接口占用还是RAM侧指针差必须先确认。

ADC 等不可停顿源须单独设计预留空间、整包结束、溢出报告及丢弃策略，不能依靠 FIFO 自动解决丢样。N310/X4xx radio RX 的 `space<5` 是该实例的在途预留，不是统一阈值。可以按设计丢弃的诊断错误与归还 DMA 所有权必需的完成记录分开：后者必须预留容量或背压，禁止满时静默丢弃。

## 3. BRAM：可读与排空必须分开

同步RAM读有延迟，预取寄存器中可能仍有有效数据。`!o_tvalid`可能只代表当前无可读word，不能自动当作整个队列无pending；RAM侧empty也不一定意味着输出/预取级已清空。只有RAM内容、预取、输出以及已发读请求均结算，才可据相应契约报告drained。

不要用等待固定几拍或单个不明语义occupied计数替代该条件。`axi_fifo_bram` 上游注明 `space/occupied` 为诊断信息，不保证精确；需要精确逻辑容量、fence 或所有权结算时，用接口实际接受数减实际消费数，并单独结算明确取消丢弃。在stop/flush、CDC重启、packetizer排空和DMA取消中尤其要检查：最后一个word由外部实际valid&&ready后才能归还槽，不是预取到RAM输出就释放。

`axis_packet_flush.done` 来自静默超时，不能证明上游全部事务完成。PCIe STOP/CANCEL 还必须结算真实 MRd/Cpl/MWr 及完成记录账本、排空整 TLP，之后才能归还主机缓冲。

## 4. CDC、业务bundle与复位

异步FIFO中timestamp、样本、mask/epoch相关元信息及SOB/EOB作为一个不可分bundle跨域；不能分别两级同步后重新拼包。采用Gray指针时检查源端编码与目标器件要求的总线时延/skew约束，ASYNC_REG不能替代电路或约束。

如果按包拆分 metadata 与 payload，必须有显式配对和消费契约：参考 `chdr_to_axis_data`，二者同时有效才释放 payload，metadata 在最后一个 payload 的实际握手时弹出。定时 RX/TX 的目标时间与命令属性一起排队，由源采样域状态机判断执行与迟到，不能在出队后重贴时间戳。

已核对的 `axi_fifo_2clk` **公共接口只有一个 `reset`**，`i_arst/o_arst` 是内部经各时钟域同步的信号，不是两个可独立驱动的公共复位口。复位事件必须足够长并能被两域可靠观察；时钟暂停时先保证恢复后的复位传播与完成，再开放业务。封装不提供任意单边 reset/clear 的会话清理保证。

两域复位必须有明确启动互锁；一边reset、另一边仍持有旧数据时不能直接认为新会话已干净。只清一个FIFO指针不能取消已经发出的PCIe MRd/MWr，也不能证明主机缓冲可释放。

## 5. 仿真先行验收

先写自检testbench与独立数据scoreboard，运行后再写/改可综合适配层。针对每项接口差异观察失败，再验证修复；不只比较新旧两个FIFO，因为它们可能共同违反契约。

至少覆盖：

- reset/clear前后，非空/反压中reset，reset期间禁止握手，invalid旧payload不泄漏；
- 空队列首写延迟、单项替换、连续一拍一字、长stall后恢复；
- 全满/空读/满写、full+pop+push、指针回绕、不同逻辑capacity、宽度及多个随机seed；
- data与timestamp/标签逐项一致，接受数=输出数+剩余数（reset/明确取消丢弃另计）；
- BRAM预取尚未到输出、输出stall、最后一拍，验证readable/pending/drained不是混用；
- 异步FIFO的时钟比/相位、两域reset顺序、时钟暂停及背压；
- 集成后的真实生产者/消费者，包括完成事件容量预留与peer隔离，而非只测wrapper。

用真实目标原语功能模型；SRLC32E的Vivado模型有初始化窗口，应在窗口结束后做受控runtime reset再开始检查，不能用空壳模型或关闭断言掩盖。Icarus需要显式编译依赖和原语模型；Vivado不将仿真原语源码当成自有综合源码加入。

模块/集成仿真通过后才进入综合和候选bit；再检查资源推断、时序/CDC/DRC。仿真不能证明STA、亚稳态MTBF或物理实现稳定。已有project用Tcl添加源码，不新建工程或放宽XDC来绕过问题；bit下载与提交遵守用户的独立确认规则。

## 6. 需要 Xilinx IP 时：通过 Tcl 接入现有工程

先确认具体版本与目标器件。以下是已核对 UHD 版本中 `axi_fifo_2clk` 默认 `DEVICE="7SERIES"` 分支的示例，不能作为所有厂商/版本的统一参数：

| IP 模块名 | FIFO Generator 实现 | 数据位宽 | 配置深度 | 读出模式 |
| --- | --- | --- | --- | --- |
| `fifo_short_2clk` | `Independent_Clocks_Distributed_RAM` | 72 | 32 | `First_Word_Fall_Through` |
| `fifo_4k_2clk` | `Independent_Clocks_Block_RAM` | 72 | 512 | `First_Word_Fall_Through` |

两者已核对 XCI 的 `Enable_Reset_Synchronization=true`、`Reset_Type=Asynchronous_Reset`、`Full_Flags_Reset_Value=1`。位宽/深度对应输入和输出两侧；这些是 IP 配置值，FWFT、流水级、扩展队列会影响端到端可用容量。不要根据 `4k` 名称推断深度。

此分支把宽数据切成 72 bit lane，所有 lane 同时可写/可读才统一推进。`SIZE<=5` 使用固定 short IP，`SIZE=6..9` 使用固定 BRAM IP，`SIZE>9` 再串联输出域 flop2 与 BRAM 扩展。例：192 bit、SIZE=9、PIPELINE=NONE 在此实现中使用 3 个 72 bit lane，补齐到 216 bit 后取低 192 bit；不能为各 lane 分别推进或复位。`PIPELINE=NONE/IN/OUT/INOUT` 的容量和延迟也要纳入契约。

在项目保存可重复执行的 Tcl，按以下顺序处理：

1. 使用现有打开工程，或在没有另一进程写入时 `open_project` 原 XPR。读取 `get_property PART [current_project]`、`version -short` 及 `get_ipdefs`，确定实际支持的 FIFO Generator 版本和配置属性；不照搬其他板卡综合后的 DCP/netlist，不静默 `upgrade_ip`。工程正被 GUI/其他构建写入时，使用该工程拥有者执行脚本，避免两个进程同时保存/重置运行。
2. 通过 `add_files -norecurse` 添加项目 vendor 中的完整依赖；已存在的文件不重复添加。设置 include 路径和仿真/综合用途。`axi_fifo_2clk` 需要 `synchronizer/synchronizer_impl` 及所选 IP，按分支还需 flop2、BRAM、ram_2port 和头文件。仿真原语模型不作为自有综合源码加入。
3. 用 `get_ips -quiet` 查同名 IP；若 XCI 已在项目目录但尚未注册，先 `read_ip`，不能直接覆盖。确实不存在时，使用 `create_ip -name fifo_generator -vendor xilinx.com -library ip -version $ip_version -module_name $ip_name -dir $ip_dir` 创建，变量从项目配置取得，目录放在项目管理范围。
4. 对新 IP 用 `set_property -dict` 显式设置已核对的 `CONFIG.Fifo_Implementation`、`CONFIG.Input_Data_Width`、`CONFIG.Output_Data_Width`、`CONFIG.Input_Depth`、`CONFIG.Output_Depth`、`CONFIG.Performance_Options` 及复位/端口配置；用 `list_property/get_property` 检查当前版本可用属性及最终值。保留封装需要的全部端口，不能只核对位宽/深度就认为兼容。已有 IP 则比较 VLNV、目标及完整配置，不符时明确报错并说明差异；只有任务明确包含迁移时才更新配置。
5. 运行 `report_ip_status`，按项目方式执行 `generate_target all [get_ips $ip_name]`，必要时 `export_ip_user_files`；更新 `update_compile_order -fileset sources_1` 和 `sim_1`。运行项目已有的仿真/综合流程；OOC 流程按需 `create_ip_run`，不顺手重置无关 runs。二次执行脚本应复用同一 IP，不产生重复模块或擅自改配置。
6. 将创建脚本、配置/XCI、来源 revision/hash/许可证纳入可复现输入；保存工具版本、目标 part、配置核验和仿真/综合结果。新建 IP 的功能模型可先生成供仿真；模块与集成仿真通过后再综合整个设计、生成候选 bit。检查黑盒/重复定义、实际资源、IP 自带约束、STA/CDC/DRC，不用新增宽泛 false-path 或放宽原 XDC 掩盖问题。

## 7. 可复核实例（参考，不作为全局固定路径）

已核对 UHD revision：`cf78e1cfd50740f2168deb94b5fe85d7ef498a12`。N310（n3xx）与 X4xx 的主要参考在公共 `lib/fifo`、`lib/rfnoc/core` 和 `lib/rfnoc/blocks/rfnoc_block_radio`，不能只搜索 top。对应异步 IP 配置在 `top/n3xx/ip` 与 `top/x400/ip` 下的 `fifo_short_2clk`、`fifo_4k_2clk`。

Radio RX 把 `{EOB, timestamp, TLAST, samples}` 同项入队，shell 通过 `chdr_to_axis_data/axis_data_to_chdr` 管理跨域及包关联。X4xx full RF core 某处 flop2 的 `reset/clear=0`、输出 `ready=1` 是始终消费的 ADC 流水实例，不适用于可背压且需会话 flush 的队列；radio TX 允许丢新诊断错误的 FIFO 也不能照搬为 DMA 完成队列。

上游来源为 `EttusResearch/uhd` 仓库；上述路径相对于其 `fpga/usrp3/`。公共 FIFO 完整目录为 `fpga/usrp3/lib/fifo/`，核对时使用上述 revision。

U230 项目参考（路径相对于项目根目录）：`fpga/vendor/ettus/` 中的 README/source-manifest/LICENSE；`fpga/src/fifo/pcie_ettus_head_fifo32.v`保持固定32项、同步高有效reset、满写不接受/空读忽略和occupied>=31的本地almost_full语义。该阈值仅适合这个wrapper，不向BRAM版泛化。工程已有`fpga/scripts/sim/run_ettus_head_fifo32_tb.sh`可用独立OUT_FILE执行，避免覆盖旧证据。

本仓库只附复用与适配指南，不附 UHD RTL、Xilinx IP 产物或 U230 工程；这些项目相对路径用于溯源，不是安装依赖。不要求其他项目存在同样布局，也不授权自动下载 bit 或修改系统驱动。
