# BetterTDRender（BTDR）实现参考 · 第 2 份

第 1 份 `IMPLEMENTATION.md`（§0–§9b，含维护规则）、第 1b 份 `IMPLEMENTATION_1b.md`（§9c–§9g）。本份：性能、已知的坑、测试、开发者流程、尚未实现、变更记录。

## 10. 性能（5080 Laptop，1080p，示例场景，Quality = High）

预算：High 档 GPU ≤ 5 ms、CPU ≤ 1.5 ms；Low 档 GPU ≤ 3 ms。每个里程碑的实测值记在文末变更记录里。

测量工具：`tools/perf_bench.py`。一次只拉取一个渲染器的输出，每帧把它内部本帧计算过的节点的 `gpuCookTime` / `cookTime` 加起来，
预热 40 帧后取 180 帧的中位数。结果写 `out/perf_bench.txt`。场景：示例场景，60 万三角形、4K 贴图。

0.1.x–0.2.0 的历次实测和当时的分析（G-Buffer 改 16 位、阴影缓存、M2 镜头效果等）移到了 `PERF_HISTORY.md`。

**0.6.0 透明（M6a）实测（2026-11-12，`tests/m6_scene.py`：5 个透明物体约占画面 1/3，`cpu_profile.py`）：** GPU `tgbuffer` 0.18 ms、`tback` 0.09、`refract` 0.34，合计约 0.6 ms；CPU `tgbuffer` 0.37、`tback` 0.23、`refract` 0.09、7 个 Render Select 约 0.18，合计约 0.85 ms。没有透明物体时 0（A/B 见 §9e）。`tback2` 的 GPU 读数 5.2 ms 是等待 GPU 队列的时间算到它头上（§11 第 17 条），不是它的开销。CPU 的大头是两个额外的 Render TOP；把 RT4 并进 RT0.a / RT2.a 可以省一个 Render Select。

**0.7.0 光追折射（M6c）实测（2026-11-12，`tests/m6_scene.py`，Hybrid）：** `rt_refr` GPU 0.03 / CPU 0.14 ms，累积和 POP to TOP 约 0.1 ms CPU：合计 CPU 约 +0.25 ms、GPU 约 +0.1 ms；Screen Space 时 0。

**M6b 混合透明（默认不构建）实测（2026-11-12，`tests/m6b_scene.py`：7 张烟雾贴片、362 个实例化火花、全息盒，加 1 个玻璃球，`cpu_profile.py`）：** `tblend` CPU 0.22 / GPU 0.21 ms，`ub_tex` CPU 0.08，3 个前向材质各约 0.03（每帧计算，§11 第 40 条），`blend_comp` 0.03 / 0.03：合计 CPU 约 +0.45 ms、GPU 约 +0.25 ms。没有混合类物体时 0（A/B 见 §9f）。整个测试场景（折射 + 混合 + 默认全部效果）CPU 2.1 ms、GPU 2.9 ms。

**0.5.1 全局性能审查（2026-11-12，demo 场景：雾和运动模糊开，`cpu_profile.py` 只统计每帧都计算的节点）：**

| | 0.5.0 | 0.5.1 |
|---|---|---|
| CPU（每帧计算的节点合计） | 2.13 ms | 1.94 ms |
| GPU（去掉 gbuf0 等待） | 2.19 ms | 2.16 ms |
| 每帧计算的节点数 | 58 | 50 |

- 改动（都不改变画面，`tools/ab_compare.py` 验证：最终画面平均 |差| 0.0004，只在轮廓的单像素上）：`uniforms` 缓存 Par 对象、`rt_static` 键不再逐值取整（0.54 → 0.45 ms）；自动曝光关时测光链不计算（−0.1 ms）；光照合进 composite（−4 个 TOP；5080 上 GPU 只省 0.03 ms，带宽小的卡省得多，按 4060 Laptop 的带宽估约 0.2–0.4 ms，未实测）。
- CPU 的结构：Python（`uniforms`）0.45 ms、G-Buffer Render TOP 0.31 ms（随几何体数增长）、光追反射 GLSL POP 0.14 ms，其余是约 45 个 TOP 每个 0.02–0.07 ms 的固定开销——**TOP 的个数**才是剩下的主要 CPU 成本（Bloom 13 个约 0.3 ms）。
- GPU 的结构：`ssgi` 0.54、`ssr` 0.53（两项占一半），`composite` 0.32，`gbuffer` 0.2，`taa` 0.11。

**审查中测过、没有采用的方案：**

| 方案 | 结果 | 结论 |
|---|---|---|
| SSGI / SSR 改读单通道深度（由深度 + 相机射线重建位置，代替 8 字节的 rgba16float 位置） | 重建误差和 16 位位置本身同量级（相对误差中位数 7e-5，要用 G-Buffer 当帧的抖动）；R32F 深度：`ssgi` 0.535 → 0.536 ms，R16F：0.53 → 0.47 ms，但要多一个深度 pass（GPU 0.014、CPU 约 0.02 ms）和抖动对齐的风险 | 不采用：这两个 pass 不是带宽瓶颈，是 ALU / 延迟瓶颈 |
| Bloom 降采样改用硬件 mipmap、升采样合成一个 pass（13 个 TOP → 2–3 个） | 未实现：盒式 mipmap 会让小亮点闪烁（13 点滤波 + Karis 正是为此），合成升采样不是逐位等价 | 不满足"不影响画面"；可以作为以后 Low 档的选项 |
| ssgi_acc / ssr_acc 合成一个双输出 pass | 估计 CPU −0.03 ms | 收益太小，暂不做 |
| 静态画面冻结（相机、场景、参数都不变时停在收敛后的画面） | 未实现 | TD 的作品大多一直在动；颗粒、雾的噪声动画会停，属于行为变化 |

0.3.0（M3）、0.4.0（M4）的整套实测表移到了 `PERF_HISTORY.md`。

剩下的方向：
- 1080p 到 2160p 像素是 4 倍，GPU 是 4 倍（M3 的屏幕空间 pass 和像素数成正比）。
- 其他显卡的估算按 3DMark Time Spy 显卡分换算，只能当量级参考，见使用手册的性能一节。

## 11. 已知的坑

1. POP 几何体必须用 `TDPos()` 这组函数取属性（§6）。
2. 菜单参数在表达式里 `int(par)` 得到的是菜单序号，不是菜单项的名字；要用 `int(par.eval())`（阴影分辨率踩过，结果是 2×2 的阴影图）。
3. 同一帧里改参数再 `cook(force=True)`，下游拿到的还是旧值；验证脚本要用 `run(..., delayFrames=N)` 隔几帧再读。
4. 脚本新建 GLSL TOP / MAT 会带停靠的模板 DAT；销毁宿主时它们一起消失，遍历 `children` 销毁时要先判断 `valid`。
5. OP 类型的参数用表达式绑定时，源为空会得到 `None` 并报"Invalid path"警告；表达式要写成 `….eval() or ''`。
6. 自定义的 OBJ 类型参数，相对路径是相对于**组件的父网络**解析的（`cam1` 指同级的 cam1），正好和原生 Render TOP 一致。
7. MCP 的 `execute_code` 返回值会被截断；长结果写到 `btdr/out/*.txt` 再取回。
8. Render TOP 被拉取时每帧都会重画，和场景是否变化无关（用 `totalCooks` 实测）。别指望靠"输入没变"省掉 G-Buffer 或阴影图；要省就在后面接一个不激活的 Cache TOP，让它不再被拉取（阴影图缓存就是这么做的，§5）。
9. 给 Render TOP 的 Vectors 页设 uniform 可以传进材质，但材质节点会一直报"Uniform is not assigned"警告，并冒泡到组件上；0.1.2 因此让抖动从 GLSL MAT 的数组 uniform 读 `jitter` CHOP；0.2.0 起抖动改放在 `cam_jit` 的投影里，材质完全不碰抖动（`EXT.JITCAM`）。
10. `addWarning` 只能在节点计算过程中调用；在扩展方法里（参数回调、`run` 延时调用）直接调会抛 `Cannot set warning outside of cook`。0.1.0 因此在有警告时 `Refresh()` 中途异常、状态没存上，由回归测试发现，0.1.1 修复。
11. `scriptOp.copyNumpyArray()` 要求数组是 C 连续的（转置后的数组要包一层 `np.ascontiguousarray`）。
    不满足时会抛异常，但 Script CHOP 上**不显示任何错误**，只是没有通道，所有着色器读到全 0。0.1.2 开发中踩过，回归测试加了"uniform block"一项（现在是 4 × 40）。
12. 示例场景的 `cam1` 可能被设了环绕路径（Xform 页 Path SOP = `circle1`，Position 用 `absTime` 驱动）：直接改 `tx/ty/tz` 没用。
    `tools/shots.py` 截图时会临时去掉路径，结束后恢复。
13. 一帧里各节点的计算顺序：一个 TOP 先计算输入，再计算参数引用的 CHOP（`lighting` 的输入早于 `uniforms`，见 §5 阴影图缓存）。依赖这个顺序的地方都写了注释。
14. 负载重的时候（Refresh、着色器编译）一次计算可能跳过十几个时间线帧，`run(..., delayFrames=N)` 到点时实际可能只算了一两帧。测试里依赖"变化已稳定"的检查要轮询状态，不能只靠延时（Quality Low 一项踩过）。
15. 旧管线文档 §12 的坑（Feedback TOP 依赖环、TOP 按需计算、GLSL POP 重建加速结构等）在移植 M3–M4 时同样适用。
16. 在帧开始的 `run()` 回调里读一个"每帧计算"的 CHOP 或 TOP，会让它在这一帧多计算一次（时间线已经前进了，正常的计算还没开始）。依赖"上一帧"状态的节点要防这种重复计算（`UNI.RECOOK`）。调试时要读这类节点的值，最好直接在 MCP 的 `execute_code` 里读，或者在回调里只读不触发计算的东西。
17. TD 的 GPU 计时（`gpuCookTime`）会把等 GPU 队列的时间算到第一个等结果的节点头上：示例场景里 `gbuf0`（G-Buffer 后第一个 Render Select）在不同时段从 0.03 ms 到 7 ms 不等，画面和设置都没变。`tools/perf_bench.py` 单独列出"去掉 gbuf0 等待"的数字（`BENCH.SYNC`）。
18. 带原生阴影（Shadow Type ≠ Off）的 Light COMP 在示例场景里每帧都会重新计算并画自己的阴影图（约 0.25 ms CPU、1.4 ms GPU），即使 BTDR 不在计算。BTDR 读灯的变换时会把这次计算算进 `uniforms` 的耗时。只用 BTDR 时可以把灯的 Shadow Type 设成 Off；BTDR 的阴影是自己画的，不受影响。
19. **3D 输出的 GLSL TOP（像素着色器模式）里，uniform 数组只有第一个切片是对的**：后面的切片读到的是错位的数据（实测 TD 2025.33230：`uB[32].y` 在第 0 片是 40，第 1、2 片是 0，之后是别的槽位的值）。症状是雾全是 NaN、画面全黑。纹理缓冲（Array Type = Texture Buffer）所有切片都对；计算着色器也照样用纹理缓冲（`BUILD.TBUF`）。
20. 3D 纹理作为输入时深度方向是重复寻址的，查 s = 1 会混进第一片（`FOG.EDGE`）。
21. GLSL TOP 的计算着色器：模式 Compute，代码放 Compute Shader DAT，`TDImageStoreOutput(0, uvec3(...), color)` 写输出；关掉 Auto Dispatch Size 自己算分组数。计算着色器里没有导数，采样纹理要用 `textureLod`。
22. 屏幕空间 pass 读"上一帧"（`taa_hist`）时，任何写进 TAA 输入的东西都会反馈回来：调试画面、NaN。所以调试画面放在 `debug` pass，TAA 和累积 pass 都有 NaN 保护。
23. **Script CHOP 在 Python 回调里读 `absTime` 不会让它每帧计算**，只有参数表达式引用 `absTime` 才会。0.3.1 及以前 `uniforms` 只靠回调里的 `absTime.frame`：示例场景的相机一直在动，`uniforms` 跟着相机重算，看不出问题；相机静止时它只算一次——帧号停在 0、历史重置标志一直是 1、TAA 抖动停在第一个样本，TAA / AO / 反弹光 / 反射 / 雾的时间累积全部失效（画面发噪），阴影图的变化检测也停了（改 SOP 后阴影不更新）。0.3.2 加了 `BUILD.UNICOOK`，测试 `TEST.STILLCAM` 防回归。
24. 测试网络里的 BTDR 没人看就不计算（TOP 按需计算），这时截图只算了一两帧，历史还没累积。手动测试时要让输出一直被拉取（`/project1/fog_test/keep_cooking` 的做法：帧开始回调里 `out1.cook()`）。
25. 设备提交（`device_commit_files`）同一暂存路径连续提交时，偶尔要隔一会儿才生效，或者不生效；改完马上 `exec` 的脚本可能还是旧版本。提交后在 TD 里读文件确认（或按 §0 用新的暂存文件名；`tools/apply_stage.py` 按清单校验 md5）。
26. **GLSL POP 会自己声明 Arrays 页的数组**：着色器里再写 `uniform samplerBuffer rtMat;` 会报重复定义。（`common.glsl` 的 `uniform vec4 uB[40];` 却不冲突，GLSL TOP 也不冲突。）
27. 加速结构只接受三角形：四边形会让 GLSL POP 报"POP for acceleration structure must have triangles only"。Triangulate POP 是给线条用的，三角化四边形要用 Convert POP 的 Quads to Triangles。
28. GLSL POP 每次计算都重建加速结构；Build Flag = Fast Trace 比 Fast Build 慢一个数量级以上（3.2 万面 0.65 ms 对 0.03 ms）。每帧算的 pass 用 Fast Build（`BUILD.RTAS`）。
29. Transform POP 的 Xform Matrix/CHOP/DAT 不接受 COMP（警告 "must be: DAT CHOP"，并且不变换）；用 4×4 Table DAT，行主序。
30. Grid SOP 默认输出 mesh 图元，SOP to POP 后是 0 个图元；先 Convert SOP 转多边形。
31. 新建 GLSL POP 时编译错误可能残留到它下次计算：只在变化时计算的节点（探针）上读 `errors()` 前要先 `cook(force=True)`（`UNI.RTCHECK`）。
32. **Feedback TOP 在第一次被目标覆盖之前的内容是未初始化的显存**（不是黑色）。渲染器拖进一个没人看的网络、过一阵才第一次被拉取时，历史重置帧的 SSR / SSGI 从 `taa_hist` 读到的是垃圾（彩色亮点），经过反射链自己维持下去，示例网络第一次打开时满屏彩色噪点（0.4.0）。一直被拉取的渲染器看不出来：那块显存碰巧是上一次的有效画面。修复 `SS.HISTRESET`；测试 `TEST.COLDSTART`。Feedback 的其他读者（TAA、累积、自动曝光）本来就在重置帧不读历史。
33. Sphere SOP 的 Primitive Type = Polygon 用 **Frequency**（默认 2，80 个面），Rows / Cols 只对 Mesh 等类型有效。
34. **`inputConnectors[i].connections` 拿到的是上游节点的输出口**；对它调 `disconnect()` 会剪掉那个上游输出的**所有**连线。0.5.1 审查时用它断开一个复制节点的输入，结果把 gbuf1 / gbuf2 / taa_hist 到 ssgi、ssr、taa 的连线全剪了（画面变成 TD 着色器出错时的红蓝棋盘格），用 hotswap 恢复。断开某个节点自己的输入用 `node.inputConnectors[i].disconnect()`；做原型放在渲染器外面的独立网络里。
35. 计时陷阱：对一个输入没变的 TOP `cook(force=True)`，它的 `gpuCookTime` 约 0.02 ms——GPU 上并没有重新执行。比较两个 pass 的 GPU 时间时，两个都要接一个每帧都变的输入（`ab_compare.py` 之外的手工计时都要注意）。帧开始第一个被强制计算的 GPU 节点还会吃掉等待时间，先算一个无关的节点垫底。
36. 示例网络（`BTDR_Example.tox`）里内嵌了一份 `renderBTDR`：重新构建后要重新生成示例（`make_example.py`），A/B 测试要把两边的渲染器都换掉（`ab_compare.py` 是这样做的）。
37. **不要把 Python 函数存进 OP 的 storage**（`op.store('x', func)`）：存 .toe / .tox 时 storage 要 pickle，函数存不进去，TD 弹出 "saved with errors: PicklingError: Can't pickle <function …>"。0.5.1 的测试脚本和 `make_example.py` 都踩过（用户存盘时报错）。延时回调要用的函数，用完马上 `unstore`（`EXAMPLE.NOSTORE`），或者把临时数据存在用完就删的测试网络上；测试结束清理 `/project1` 上的临时键。
38. 自定义序列参数（`page.appendSequence`）**最少 1 块**（`numBlocks = 0` 抛 "Minimum size is 1 block"）；在 appendSequence 之后追加的参数进入块，名字自动变成 `<序列名><序号><小写的基础名>`（追加 `Geo` 得到 `Refr0geo`；追加时写了完整名字会变成 `Refr0refr0geo`），再设 `blockSize`。
39. GLSL MAT 的输出数可以多于 Render TOP 的颜色缓冲数：多出的 `layout(location = 4)` 被丢弃，不报错（`gbuffer.frag` 同时供 4 缓冲的 `gbuffer` 和 5 缓冲的 `tgbuffer` 使用）。
40. **GLSL MAT 的采样器引用的 TOP 每帧计算时，MAT 也每帧计算**（实测 `totalCooks` 每帧 +1），和 uniform 数组绑 CHOP 一样。想让材质不重算，材质里就不能引用任何每帧变化的 OP——M1–M6a 的材质都做到了（`GBUF.SHARED`），混合类的前向材质做不到（要读深度、阴影），代价每个约 0.03 ms CPU。
41. Sphere SOP 的 Primitive Type 菜单名是 `prim / poly / mesh / nurbs / bezier`：写 `'polygon'` 不报错、保持默认的 `prim`（一个点、一个图元），拿它做实例化源只有 1 个实例。Ramp TOP 的 Circular 模式默认 Extend = Repeat，超过半径的角落会重复出圆环，做柔和的圆形贴图要把 Extend Left / Right 设成 Hold。
42. PolyReduce SOP 的 Keep % 对低模物体是灾难：6 个面的盒子 15% 只剩 1 个三角形。另外 Keep # 数的是 Pre-Triangulate 之后的三角形（四边形算两个）。SOP 的 `numPrims` 是属性、POP 的 `numPrims()` 是方法，表达式里写错会报 "'int' object is not callable"。（`EXT.RTMINPOLY`）
43. 新建的 GLSL POP 在前几帧（尤其负载重时）输出的属性可能是未初始化的值，经 POP to TOP 进入画面就是负数、NaN 的斑点。读 GLSL POP 结果的地方都要做有限值 / 范围检查（`REFR.RT`）。
44. GLSL POP 只把 Output Attributes 里列出的属性声明成可写数组：写输入就有的 `P` 要在 Output Attributes 里写上 `P`（默认 `*` 只含新建的属性），否则编译报 "'P' : undeclared identifier"（`SCENES.PARTICLES`）。
45. 透明物体的 PBR MAT 要把 Alpha Front 设成 0：默认 1 等于不透明的漫反射涂层，玻璃看起来像白瓷。
46. 录制脚本每帧给参数赋相同的值也算"参数变了"：给灯、相机的 Look At 反复赋同一个值会让阴影图每帧重画、体积雾和时间累积每帧重置，画面满是块状噪点。`tools/video_rig.py` 只在值真的变化时赋值（`VIDEO.*`）。
47. 体积雾的“斜条纹”排查方法（0.7.3）：先用 CPU 暴力光线步进（同一张阴影图、每像素几百个采样）做参考图，再用同样的格子算法在 CPU 上模拟一遍，和 GPU 的雾体积逐项对比（`fog_apply` 去掉表面颜色的调试副本）。三者一致说明格子 / 时间累积 / 积分没错，问题在“物理模型”本身：雾里的阴影没有和表面一致的软阴影（PCSS），细遮挡物后面每一层光片都保持硬边，几米外仍是清晰的条带。另：`fog_apply` 的输入 0 是表面颜色，拿 `结果 − 输入0 × 透过率` 估算雾会把表面的东西混进来，调试雾要单独输出积分体积。
48. 着色器里用 `帧号 × 常数` 做每帧随机数：帧号只在切相机时归零，32 位浮点下乘积到 1e6 左右就没有小数精度，噪声退化成固定图案（时间累积平均不掉）。`uFrame.x` 现在按 4096 取模（`UNI.FRAMEWRAP`）。

## 11b. 测试（`tests/m1_tests.py`）

建 7 个球（每个一种材质情况）+ 地面，按帧延时依次检查，全部用数值判定（读 G-Buffer / 输出的像素）：

| 检查 | 判定方法 |
|---|---|
| 加载后自动 Refresh、无报错、着色器全部编译通过 | `status`、`errors()`、Info DAT |
| 法线贴图 | G-Buffer 法线与解析球面法线的平均夹角：有贴图 > 3°，无贴图 < 1.5° |
| 自发光贴图、Channel Source、Phong / Constant / 无材质 / 自定义材质 | 对应球区域内 G-Buffer 的平均值 |
| 三种视角设置方式、改分辨率 | 用深度输出 + 相机基向量重建世界坐标，与 G-Buffer 位置（加回相机位置）的最大误差 < 0.01（16 位 G-Buffer 下实测约 0.006） |
| uniform 数组 | `uniforms` 是 4 通道 × 40 采样 |
| 材质不读每帧数据、各向异性、抖动相机 | 镜像材质没有指向 CHOP 的数组，采样器为 4×，`gbuffer` 的相机是 `cam_jit` |
| 法线贴图约定 | 切到 DirectX 后，法线贴图球的 G-Buffer 法线平均变化 > 1° |
| Quality Low、非平行光、没有灯 | 阴影图尺寸、警告文字、直接光不为 0 |
| HDRI 环境 | 合成的 HDR 全景（天空渐变 + 亮度 60 的太阳）；画面有变化、图集无 NaN |
| 两个实例并存、保存再加载 | 各自的镜像数量、镜像指向新位置、画面与保存前一致 |
| 阴影图缓存 | 静态 10 帧内 `shadow` 最多重画 1 次且缓存未激活；转动灯光后 `shadow` 重画、直接光有变化 |
| `TEST.M2` TAA | 关：`cam_jit` 的 Window X / Y 等于用户相机、抖动槽为 0；开：抖动在 ±0.5 像素内（x 按宽度、y 按高度换算像素；0.3.2 前 y 也按宽度算，抖动停住时看不出来）、TAA 开关槽为 1、画面有限值且只有少量（边缘）像素和不开 TAA 不同 |
| `TEST.M2` 镜头效果 | Bloom、自动曝光、景深、运动模糊全开：无报错、曝光倍数有限且在 Min / Max EV 范围内、两个 Switch 都切到效果分支、景深输出和输入有差别；全关后 Switch 回到旁路 |
| `TEST.M3` 屏幕空间 | 测试场景（7 个球 + 无材质地面）：AO 有限值、最暗 < 0.8（球和地面接触处）、平均 > 0.5；SSR 置信度最大 > 0.05；两个 Switch 都在效果分支 |
| `TEST.STILLCAM` | 测试相机不动：开雾后 25 帧内 `uniforms` 的帧号至少前进 10、重置标志为 0、`fog_accum` 存在 |
| `TEST.BLOOM` | 6 级都在、¼ 和 1/128 尺寸对、`bloom_src` 在效果分支、结果有限且非负 |
| `TEST.M4` 光追 | 代理 > 100 个三角形、两个 GLSL POP 无错、探针 16×8×16 且有效比例 30%–100%、反射有命中、合成无 NaN、`uRT` 两个开关为 1、Switch 在光追分支；两个调试画面有内容；关闭后 Switch 回到常量 |
| `TEST.RTSTATIC` | 静态测试场景 18 帧内 `rt_probes` 最多计算 1 次 |
| `TEST.HFAO` | 打开后 `hf_src` 切到缓存、顶视图里球占 0.1%–50% 的像素（地面不在图里）、合成结果无 NaN；关闭后 `hf_src` 回到常量 |
| `TEST.M3` 体积雾 | 打开后 Switch 切换、雾结果无 NaN、最远切片透射率在 (0, 1) 之间、画面有变化 |
| `TEST.M3` 调试画面、关闭 | AO 和反射的 Debug View 有内容、无 NaN；全部关闭后三个 Switch 回到旁路 |

几何相关的检查（视角、分辨率、法线等）在 TAA 关闭下做，因为它们拿不含抖动的相机重建位置；TAA 单独在 `TEST.M2` 里测。

TD 自带的 Samples 里没有 HDR 全景图，所以自动测试里的 HDRI 用的是合成图。

真实 HDRI 的手动测试、示例场景的贴图和测试模型的说明（`DEMO.*` 锚点）在 `DEMO_ASSETS.md`。

## 11b-2. 验收测试（`tests/m5_acceptance.py`）

模拟用户：在空的 Base COMP 里只用原生节点照使用手册 §2.2 搭场景，拖入 `release/BTDR.tox`，不填任何参数。

| 检查 | 判定方法 |
|---|---|
| 自动找到相机、灯、几何体 | `status` 里的 camera / light 以 `cam1` / `light1` 结尾，镜像 1 个 |
| 无警告、无报错 | `status` 的 warnings 为空，所有子节点 `errors()` 为空 |
| 画面 | 有限值、std > 0.02、最大值 > 0.3 |
| 光追可用且开启、版本号 | `Rtavailable`、`Raytracing`、`Version` 以 0.5 开头 |
| `TEST.COLDSTART` | 载入 `release/BTDR_Example.tox`、关掉它的 `keep_cooking`，60 帧没人拉取后第一次 `cook(force=True)` 的画面，和再连续拉取 60 帧后的画面比：平均差 < 0.08、饱和像素 < 5%、无 NaN（0.4.0 时这张图满是彩色亮点，§11 第 32 条） |

0.5.0：7 项全过，从空网络到最后一项检查约 4.5 s（含 210 帧等待）。

## 11b-3. M6 透明测试（`tests/m6_tests.py`）

在 `tests/m6_scene.py` 的场景上检查：5 个槽都解析到、镜像是 `t*`、三个 Switch 打开、无报错、`refract` 全是有限值、玻璃像素占比 > 2% 且画面有变化、**非玻璃像素和 composite 完全一样**、背面有内容、玻璃默认不进阴影列表；关掉 Transparency 后 `Transcount` 为 0、Switch 旁路、`refract` 不再计算；选 Diamond 预设后 IOR = 2.42。`TEST.M6C`（0.7.0）：Screen Space 时 `rtr_src` 旁路；切到 Ray Traced 后无报错、`rtr_src` 打开且 `uRT4.w` = 2、`out_t` 比 `out` 多（玻璃只在折射场景）、光追有效像素 5%–90%、有限且平均亮度 > 0.05（不是全黑）、`refract` 有限；切回 Screen Space 后 `rt_refr` 不再计算。0.7.0：全过。

## 11b-4. M6b 混合透明测试（`tests/m6b_tests.py`，只在 `M6B = True` 的构建上能跑）

在 `tests/m6b_scene.py` 的场景上检查：9 个混合类物体（7 个由 PBR MAT 自动识别、2 个来自 Blended 槽）、玻璃仍是折射类、镜像是 `b*`、`blend_src` 打开、无报错、`ub_tex` 和 `uniforms` 逐值一致、`tblend` 有限值且 alpha ≤ 1、烟雾覆盖率在 5%–90%、存在叠加像素（rgb 亮、alpha 为 0）、**没有混合类的像素和 `trans_src` 完全一样**、混合类不进阴影列表；切到 Order Independent 后无报错、Render TOP 模式正确、有画面；关掉 Transparency 后 `Blendcount` 为 0、Switch 旁路、`tblend` 不再计算。0.7.0：全过。

## 11c. 开发者流程

都在 Textport（Alt+T）里执行，结果写 `btdr/out/`，第一行是 `STATUS ...`：

| 步骤 | 命令 | 结果 |
|---|---|---|
| 构建 | `exec(open(project.folder + '/btdr/build.py', encoding='utf-8').read())` | `release/BTDR.tox`，并复制到 Palette（`BUILD.PALETTE`）；`out/build_log.txt` |
| 替换工程里的实例 | `tools/hotswap.py`（`HOTSWAP_TARGETS` 指定多个，`HOTSWAP_NOBUILD` 跳过构建） | 参数和连线保留 |
| 回归测试 | `tests/m1_tests.py` | 约 20 秒，39 项；测试网络自动删除 |
| 透明测试 | `tests/m6_tests.py`（测试场景单独搭：`tests/m6_scene.py`，`M6_SHOT = 'tag'` 存 `out/m6_<tag>.jpg`） | §11b-3 |
| 混合透明测试 | `tests/m6b_tests.py`（场景：`tests/m6b_scene.py`，`M6_SHOT` 存 `out/m6b_<tag>.jpg`） | §11b-4 |
| 演示场景 | `examples/demo_scene.py` | `/project1/btdr_demo`：测试模型 AntiqueCamera + FlightHelmet（`测试模型/`，CC0）、HDRI（Rotate −96.2 对齐 light1）、原生 Render TOP 对照 `native_render`；贴图在 `/project1/tex_lib`。素材说明见 `DEMO_ASSETS.md` |
| 发布用示例 | `examples/make_example.py` | `/project1/btdr_example`，存 `examples/` 和 `release/` 的 `BTDR_Example.tox`（`EXAMPLE.*`） |
| 验收 | `tests/m5_acceptance.py` | §11b-2 |
| 画面 A/B | `tools/ab_compare.py`（先把旧构建复制成 `release/BTDR_ref.tox`） | `out/ab_compare.txt`、`out/ab_A.jpg` / `ab_B.jpg`；性能类改动要求最终画面看不出差别 |
| 展示工程 | 在目标工程（它的文件夹就是包）里：`SHOW_SRC = '<源码>/btdr'`，再 exec `<源码>/btdr/examples/make_showcase.py` | 拷入 BTDR.tox、BTDR_Example.tox、`Image/` 下的 HDRI、USER_GUIDE.md、README.txt，建 `/project1/showcase`（4 个预设：Studio / HDRI / Volumetric Fog / Night，`SHOWCASE.*`）；HDRI 用相对路径，整个文件夹可以搬走。2026-11-12 生成了 `F:/Projects/Touchdesigner Projects/BetterTDRender/BetterTDRender.toe` |
| 打包 | `tools/make_release.py` | `release/BTDR_<版本>.zip`：BTDR.tox、BTDR_Example.tox、USER_GUIDE.md、README.txt（源文件 `docs/RELEASE_README.txt`）、`hdri/`；`out/release_log.txt` 列出每个文件的 md5 |

发布顺序：构建 → 回归测试 → 示例 → 验收 → 打包。

示例网络（`EXAMPLE.*`）的取舍：只用 TD 自带的 SOP 和原生 PBR MAT，不带任何外部文件；相机在场景前方 ±55° 摆动（转到墙后面会看到墙背面）；灯的原生阴影关掉；Bloom 0.15 让发光方块有光晕；`keep_cooking`（帧开始时拉取 OUT）存盘前关掉，用户打开时按需计算。

## 12. 尚未实现

- M5 遗留：示例网络的 4060 / 2060 实测；Palette 安装说明以外的安装方式（TD 的 Package / 组件库）。
- M4 遗留：实例化几何体进光追代理；命中点用逐纹素的贴图颜色（现在是每物体平均色）和高光；探针可见性（DDGI 的深度矩，防薄墙漏光）；光追阴影；探针多次反弹；不支持光追的机器上实测降级路径。
- M3 遗留：High 档 SSGI 半分辨率 + 深度感知上采样；雾里的局部光源；屏幕空间光束（太阳在画面里时的径向光芒，便宜的补充）。
- M2 遗留：物体运动矢量（物体自身运动的运动模糊、TAA 更少拖影）、景深的散景形状（目前是圆盘）、镜头切换的自动检测（现在只在换相机节点时重置历史）。
- M6 遗留：M6a 剩余项见 §9e 末尾；M6b 混合透明默认不构建（§9f 写了要改进的地方）；M6c：命中点用贴图颜色、色散、光追玻璃投彩色阴影（焦散）。
- 之后：多盏灯、点光 / 聚光、贴图平铺 / 偏移、嵌套几何体、场景变化自动检测。

## 13. 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-11-11 | — | M0 技术验证，方案第 3 版（单节点 + 原生 PBR MAT + 场景镜像），见 `archive/ue5r/docs/TOOLKIT_PLAN.md` |
| 2026-11-12 | 0.7.3 | 雾里的太阳阴影改用和表面相同的 PCSS（`FOG.SHADOW`）：8 个遮挡搜索 + 12 个 PCF 采样，每格每帧随机旋转，半影随到遮挡物的距离变大；Fog Shadow Blur 改为“相对表面阴影的半影倍数”（1 = 一致，0 = 单点硬阴影）。原因：0.7.2 的固定 3×3 小核让百叶后的每层光片几米外仍是硬边，从斜角看就是一道道斜条纹，而地面上同样的影子是软的（多机位 + CPU 参考图对比，见 §11 #47）。帧号取模 4096（`UNI.FRAMEWRAP`，§11 #48）。百叶窗场景 Fog Shadow Blur 2.5 → 1。High 下 `fog_scatter` 0.16 → 0.27 ms |
| 2026-11-12 | 0.7.2 | 体积雾噪声控制（`FOG.QUALITY`、`BUILD.FOGQUALITY`、`BUILD.FOGRES`）：Fog 页新增 Fog Resolution（Auto / 128×72×48 … 320×180×128）、Fog Current Frame Weight（原来写死的 0.1）、Fog Jitter（格子内抖动和 `fog_apply` 切片抖动的幅度）、Fog Shadow Blur（雾的阴影查表改 3×3 PCF，间距 0.75 texel × 值，0 = 单点）；uniform 用空槽 `uDOF2.w`、`uGI.w`、`uAcc.w`。默认值下除阴影查表 2×2 → 3×3 外与 0.7.1 一致。百叶窗场景（细遮挡物）用 High / 0.04 / 0.5 / 2.5：块状噪点基本消失，光束更清楚，GPU 3.50 → 3.82 ms |
| 2026-11-12 | 0.7.1 | 实例颜色（Instance Color）乘到基础色和自发光上（`GBUF.INSTCOLOR`），实例化的粒子可以各自发光。五个展示场景 `examples/make_scenes.py`（百叶窗室内、雨夜霓虹、落日巨石阵、音频驱动的 40 万 POP 粒子、材质陈列柜，`SCENES.*`）、录制工具 `tools/video_rig.py`、场景测速 `tools/scene_bench.py`、介绍片后期脚本 `tools/video/`。场景实测（1080p High，去掉 gbuf0 等待）：GPU 3.2–4.1 ms，粒子场景 10 ms；CPU 2.0–3.2 ms。新坑 §11 第 44–46 条 |
| 2026-11-12 | 0.7.0 | M6c 光追折射（§9g）：Transparency 页 Refraction Method（Screen Space / Hybrid / Ray Traced）；玻璃进第二个光追场景 `out_t`，`rt_refr` 从前景透明层穿过玻璃代理（折射进出、全内反射、多块玻璃、按介质吸收），Hybrid 只在屏幕空间找不到背景处用光追。修 M4：光追代理减面有下限（`EXT.RTMINPOLY`），低模物体以前几乎不在光追场景里（示例网络画面因此变化：A/B 平均差 0.016，属于修正）。M6b 混合透明保留在源码、默认不构建（`BUILD.M6B`，用户决定）。回归 39 项、M6 测试（含 `TEST.M6C`）、验收全过。M6c 开销 CPU +0.25 ms、GPU +0.1 ms |
| 2026-11-12 | 0.7.0-dev | M6b 混合透明（§9f，之后改为默认不构建）：Blended 槽（Alpha / Additive、受光、软粒子覆盖），PBR MAT 开 Blending + Alpha 贴图自动识别；前向材质 `forward.frag`（无方向光照、BTDR 阴影、软粒子、玻璃后压暗），每帧数据经 `ub_tex`（uniform 块的 CHOP to TOP）读入；`tblend` 支持 Sorted / Order Independent（深度剥离）；`blend_comp` 叠在折射之后、雾和 TAA 之前。没有混合类时全部旁路（A/B 与 0.6.0 平均差 0）。回归 39 项、M6a、M6b、验收全过。测试场景 CPU +0.45 ms、GPU +0.25 ms。新坑 §11 第 40、41 条 |
| 2026-11-12 | 0.6.0 | M6a 透明与折射（`M6_TRANSPARENCY.md`，§9e）：Transparency 页的透明槽（把 Geometry COMP 拖进去，9 个预设）、从 PBR MAT 自动识别、Alpha 测试镂空；前景透明层 `tgbuffer` + 背面 `tback` 测厚度 + `refract`（两次折射、16 步深度步进找背景、按粗糙度取 mip 的磨砂、Beer-Lambert 吸收、菲涅尔、太阳高光）；合并深度给雾和 TAA。没有透明物体时全部旁路（A/B 与 0.5.1 平均差 0）。回归 39 项、M6 测试全过。透明场景 GPU +0.6 ms、CPU +0.85 ms |
| 2026-11-12 | 0.5.1 | 开源：MIT 许可（`LICENSE` 只放标准 MIT 全文，GitHub 才能识别；HDRI 的 CC0 列在 `THIRD_PARTY_NOTICES.md`），README 去掉“私有仓库”、加上测试现状和许可；使用手册 §9、发布包 README 写明许可和源码地址；`make_showcase.py` 注释里的本机路径换成占位符 |
| 2026-11-12 | 0.5.1 | 展示工程 `examples/make_showcase.py`：独立文件夹 BetterTDRender（BetterTDRender.toe + BTDR.tox + HDRI + 文档），一个程序化场景加凉棚，4 个预设可切换 / 自动轮播，体积雾预设用逆光（光束只在亮暗的雾交界、暗背景前才看得见）；预设逻辑放在 Text DAT 模块里（不往 storage 存函数，§11 第 37 条）。新坑：`connect(op)` 连到空闲输入时把 0 号输入顶掉了，要用 `inputConnectors[i]` 指定 |
| 2026-11-12 | 0.5.1 | 全局性能审查（GitHub 私有仓库 `Maxwel-Lei/BetterTDRender` 的 v0.1.0 = 0.5.0）：`uniforms` 缓存 Par 对象（`UNI.PARCACHE`）、`rt_static` 键直接比较元组（`UNI.RTSTATICKEY`）；自动曝光关闭时测光链不计算（`BUILD.AEOFF`）；光照项在 composite 里现算（`COMP.INLINE`，新文件 `lighting_core.glsl`，`lighting` 只给 Debug View）；主光开着原生阴影时 Status 给出提示（`EXT.TIPS`）。demo 场景 CPU 2.13 → 1.94 ms，每帧计算的节点 58 → 50，画面不变（新工具 `tools/ab_compare.py`）。`cpu_profile.py` 只统计每帧都计算的节点。回归测试 39 项、验收 7 项全过。审查中测过但未采用的方案见 §10 |
| 2026-11-12 | 0.5.0 | M5 发布：示例网络 `BTDR_Example.tox`（`examples/make_example.py`）、验收测试 `tests/m5_acceptance.py`（7 项全过，含 `TEST.COLDSTART`）、发布包 `release/BTDR_0.5.0.zip`（`tools/make_release.py`）。使用手册改成纯用户手册：五分钟上手、性能建议、素材建议；开发内容（演示场景、回归测试、构建）移到 §11c。修复：渲染器第一次被拉取时 SSR / SSGI 读到未初始化的 Feedback 历史，画面满是彩色亮点（`SS.HISTRESET`，§11 第 32 条）。Quality = Low 时 Bloom 少算两级（`BUILD.BLOOMLOW`）。旧管线 `ue5r/` 归档到工程目录 `archive/`，工程里的 `/project1/ue5r` 删除。回归测试 39 项全过 |
| 2026-11-12 | 0.4.0 | M4 硬件光追（简化版 Lumen）：节点内部实时生成光追代理（PolyReduce，默认保留 15%，跟随物体移动，`EXT.RTPROXY`）、探针 GI（只在场景 / 灯光变化时重算，`UNI.RTSTATIC`）、光追反射（1/4 分辨率比值法，Fast Build 加速结构 0.03 ms，`BUILD.RTAS`）、Ray Tracing 页、2 个 Debug View、不支持时自动关闭（`UNI.RTCHECK`）；uniform 槽位 36–39 用满。CarConcept 车底地面不再反射天空。回归测试 39 项全过（新增 `TEST.M4` 3 项）。1080p High 默认 GPU 约 +0.1 ms、CPU 约 +0.35 ms。新增 `tools/apply_stage.py`、`m4/rt_spike.py`；`perf_bench.py` 每种情况先回到出厂默认并计入 POP 的 GPU |
| 2026-11-12 | 0.3.5 | Bloom 改成 6 级 mip 链（`BLOOM.CHAIN`），新增 Bloom Radius；修复小亮点光晕竖长、两侧硬边（旧的 ⅛ 级没有水平模糊）。Bloom Intensity 为 0 时整条链不计算。SSR 改为在细化后的交点上做厚度测试（`SSR.REFINE`），反射边缘不再按步长出现阶梯 / 条纹。回归测试 36 项全过（新增 `TEST.BLOOM`）。实测（示例场景当前参数，雾和运动模糊开）：`ssr` GPU 0.44 → 0.52 ms（细化次数增加），Bloom 链 12 个小 TOP 的 GPU 可忽略、CPU 在测量噪声内；1080p High 默认 GPU（去掉 gbuf0 等待）2.39 ms，在 5 ms 预算内。实现参考拆成两份（§0 维护规则） |
| 2026-11-12 | 0.3.4 | Height-Field AO 只作用在接收者（地面、被罩住的面）上（`COMP.HFRECEIVER`）：0.3.3 把车身侧面也压暗了，多角度看发脏。用车底中间离地 6 cm 的机位验证：车底地面的天空反射被挡掉 |
| 2026-11-12 | 0.3.3 | 新增 Height-Field AO（Indirect 页，默认关）：顶视深度图（与阴影图同范围、同缓存）算大范围天空遮蔽，解决车底、桌下等屏幕空间 AO 看不到的遮挡（屏幕空间 AO 只知道画面里看得到的表面，车底盘朝下，相机看不到）。uniform 槽位 34–35。回归测试 35 项。超跑测试模型 CarConcept（`DEMO_ASSETS.md`），`gltf2obj.py` 处理透射、第二套 UV、贴图平铺、emissive_strength |
| 2026-11-12 | 0.3.2 | 构建时把 tox 复制进 TD 的 Palette（`BUILD.PALETTE`）。修复：相机静止时 `uniforms` 不再计算（§11 第 23 条），TAA 抖动、所有时间累积、阴影图变化检测都失效；`BUILD.UNICOOK` 让它每帧计算。新增：体积雾在 3D 格子里做时间重投影（`FOG.ACCUM`），采样点三个方向都抖动（`FOG.JITTER`），光束不再被逐格噪声淹没（GPU +0.025 ms）。测试：新增 `TEST.STILLCAM`，修正 TAA 抖动检查的 y 方向换算，34 项全过。`hotswap.py` 支持多个目标 |
| 2026-11-12 | 0.3.1 | 修复：倒影和物体之间有一条缝（`SSR.SELFHIT` 只按距离判断自相交，把贴地处的反射也丢了），现在只丢弃法线同向的近距离命中 |
| 2026-11-12 | 0.3.0 | M3：屏幕空间 AO + 反弹光（一次地平线扫描同时得到）、屏幕空间反射、时间累积、体积雾（计算着色器）；Indirect 页、Fog 页、3 个 Debug View；uniform 数组扩到 40 槽，3D pass 用纹理缓冲读（§11 第 19 条）。`taa_hist` 输入改接 `gbuf0`（避免依赖环）；TAA 和累积加 NaN 保护。回归测试 33 项全过（新增 `TEST.M3` 4 项）。1080p High 默认 GPU 1.82 ms（+1.1），体积雾 +0.1 ms |
| 2026-11-12 | 0.2.0 | M2：TAA（抖动放在内部相机 `cam_jit` 的投影里，材质不受影响）、Bloom（曝光后阈值）、自动曝光、景深、运动模糊（仅相机运动），Post 页；uniform 数组扩到 32 槽；第 2 个输出的 alpha 改为稳定视深。修复：同一帧重复计算时 `uniforms` 把上一帧相机覆盖成当前相机（`UNI.RECOOK`）。回归测试 29 项全过（新增 `TEST.M2` 4 项；几何检查改在 TAA 关闭下做）。1080p High 默认 GPU 0.69 ms / CPU 0.84 ms，全开 1.25 / 0.88。新增 `tools/variants.py`；`perf_bench.py` 单独列出去掉 gbuf0 等待的 GPU、BTDR 情况下关掉灯的原生阴影 |
| 2026-11-12 | 0.1.2 | 动态光源：运动时阴影图半分辨率、可选每 N 帧更新、每帧更新时绕过 Cache TOP；地面不进阴影渲染；修正光源运动时阴影查表基向量和阴影图差一帧。移动光源实测（同一时段）：比静止只多约 0.3 ms CPU |
| 2026-11-12 | 0.1.2 | 阴影图缓存（Light 页 Shadow Update，默认 On Change）：灯光和物体不动时不再重画阴影图；`suncam` 平移改成变化时才写入的常量。新场景 1080p High：CPU 1.41 → 0.67 ms（稳态），GPU 1.19 → 0.61 ms。回归测试 25 项全过 |
| 2026-11-12 | 0.1.2 | 示例场景换成开源测试模型（AntiqueCamera + FlightHelmet，§11d），原生对照组并进示例场景（`native_render`），删掉 `td_native`、旧贴图库内容和预览场景，工程显存约 4.8 GB → 1.0 GB。鎏金铜造像的金属度贴图改为从基础色推算（`_gilt`）。新增 `tools/gltf2obj.py`、`model_preview.py` |
| 2026-11-12 | 0.1.2 | M2 前性能优化：G-Buffer 改 16 位（位置存相对相机坐标）、镜像材质的抖动改读 `jitter` CHOP、`SunLocal` 和 `uniforms` 去 numpy。1080p High：GPU 1.55 → 1.05 ms，CPU 1.65 → 1.25 ms（预算 1.5），见 §10。新增 Render 页 Normal Map Convention（OpenGL / DirectX）、贴图 4× 各向异性过滤。示例场景 HDRI 转到太阳和灯对齐（Rotate −96.2）、背景虚化 0.1。回归测试 23 项全过。新增 `tools/cpu_profile.py`、`shots.py`、`hotswap.py` |
| 2026-11-12 | 0.1.1 | 示例场景法线强度默认 0.2（Tripo 法线贴图会重复叠加起伏）；`td_native` 去掉法线贴图，见 §11c |
| 2026-11-12 | 0.1.1 | 示例场景改用原始贴图（粗糙度、金属度、法线），贴图集中到 `/project1/tex_lib`；法线约定定为 OpenGL，见 §11c |
| 2026-11-12 | 0.1.1 | 性能实测改用 `tools/perf_bench.py`（逐渲染器单独测、取中位数），见 §10。CPU 实测 1.65 ms，此前记录的 1.0–1.3 ms 偏乐观（当时是单帧读数） |
| 2026-11-11 | 0.1.1 | 修复：有警告时 `Refresh()` 异常（见 §11 第 10 条）。新增 Status 参数、`status` DAT、回归测试 `tests/m1_tests.py`（20 项全过）。示例场景默认曝光改为 +0.5。真实 HDRI（Poly Haven，CC0）手动测试通过，见 §11b |
| 2026-11-11 | 0.1.0 | M1：`renderBTDR` 核心出图。场景镜像（SOP / POP / 实例化）、原生 PBR / Phong / Constant MAT、原生平行光、软阴影、摄影棚 / HDRI 环境、ACES、Debug View、三个输出、共享 uniform 数组。示例场景实测（5080 Laptop，1080p，High）：GPU 约 1.5–1.9 ms，CPU 约 1.0–1.3 ms（其中 Render TOP 约 0.55，`uniforms` 约 0.25） |
