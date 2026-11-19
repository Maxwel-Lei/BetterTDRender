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
50. 探针网格不能直接按包围盒均分固定的格子数：包围盒很扁时某个方向的间距会小到 0.1 m，每个探针 64 条光线的噪声在相邻层之间来回跳，平整的表面上出现一道道彩色条纹（材质场景的台子）。按形状分配格子数，让间距各向一致。
49. 雾格子在深度方向一片几十厘米厚，比百叶的光片（十几厘米间距）粗得多：每片只取一个点时光片和切片形成摩尔纹（斜带，方向和光无关）。时间抖动必须覆盖整片才能平均掉；0.7.2 给百叶场景调的 Fog Jitter 0.5 只覆盖半片，斜带就是这么来的。另：TD 里没人看的网络不计算，用 `numpyArray()` / `save()` 抓图只会强制算一帧，雾的时间累积根本没跑——测时间累积一类效果要先让网络每帧计算（`keep_cooking`）。
54. 用 `fract(sin(dot(gl_FragCoord.xy, …)))` 这类**固定在像素上的哈希**旋转采样核时，噪声每帧一样，TAA 平均不掉，会留下一层静态图案（磨砂薄膜上的淡斜纹）。要让随机数随帧变化（`uFrame.x`），最好用交错梯度噪声（`REFR.SMOOTHBLUR`）。
55. 屏幕空间里按偏移采样（模糊圆盘、折射偏移）时，采样坐标要限制在 [0, 1] 内：GLSL TOP 的输入在画面外读到 0，靠近边缘的像素平均进黑色，表现为一圈暗边（`REFR.EDGE`）。
56. **`.toe` 里的 DAT 内容可以不打开工程直接读**：复制一份 `.toe`，用 TD 自带的 `toeexpand.exe` 展开，每个 DAT 是一个 `<名字>.text` 文件（开头有 27 字节的二进制头，去掉再比较）。0.8.1 就是这样从委托工程里取出改动的。
51. **GLSL TOP 改 `numcolorbufs` 后不会重新编译着色器**：`TD_NUM_COLOR_BUFFERS` 这个宏有，但它停留在第一次编译时的值。0.8.0 的 composite 按场景在 1 / 2 张缓冲之间切换，用 `#if TD_NUM_COLOR_BUFFERS > 1` 包起来的第二个输出一直是 0。解决：输出始终声明、始终写；没有对应缓冲时这次写入被丢弃，不报错（实测）。
52. **序列参数（sequence）要手动设 `blockSize`**：`appendSequence` 之后追加的参数会进块，但 `blockSize` 是 0，`numBlocks = 2` 会报 "Could not set numBlocks…name conflicts"。`blockSize` 按**参数组**计（一个 RGB 算 1 个），Subsurface 槽是 10。
53. 刚 `loadTox` 的 BTDR，同一帧里用脚本改参数时 `parexec` 不触发（例如选 Preset 不会填值）：脚本里要等一两帧再设，或者直接写各项的值。界面上操作没有这个问题。
57. **GLSL 宏的参数名会替换掉成员访问**：`#define UM(x) ((x) * uUnit.x)` 展开后 `uUnit.x` 变成 `uUnit.(0.01)`，报 "unexpected FLOATCONSTANT"。宏参数不要用 `x / y / z / w / r / g / b / a` 这类会出现在分量名里的名字（现在叫 `m_`）。
58. **原生 PBR MAT 的 Texture Sampling Mode = Triplanar 在 TD 2025.33230 里不起作用**：SOP 上画面和 Regular 完全一样，POP 上整个表面读成贴图正中一个像素（0.8.3 用“颜色 = UV”的贴图并排实测）。Screen Space 正常：UV = 像素坐标 ÷ 分辨率。GLSL MAT 的像素着色器里没有 `uTDOutputInfo`，分辨率要自己传（`uScr`）。
59. **还没改 VERSION 就构建，会覆盖已发布版本的备份**：0.8.3 开发时第一次构建还是 0.8.2，`release/versions/BTDR_0.8.2.tox` 和 Palette 里的同名文件被开发中的版本覆盖（从 git 恢复）。现在 `release/versions/RELEASED.txt` 列出已发布的版本，`build.py` / `make_example.py` / `make_shell.py` 遇到这些版本号只构建、不写带版本号的备份（`BUILD.BACKUP`）。发布后把版本号加进这个文件。
60. 原生 PBR MAT 的 SOP Texture Coord 在 GLSL MAT 里用 `TDTexAttrib_Tex(n)` 读（等于 `TDTexCoord(n)`，下标可以是 uniform）；超出 0–1 的部分由采样器的 Extend 处理，所以 BTDR 只要把 Extend 绑到材质上，结果就和原生逐像素一致（`GBUF.UVSET`，S3 验证通过）。
61. 测试里拿“对照用的原生材质”做比较时，两边要改**同一张贴图**的参数：0.8.3 的测试第一版给原生材质改了 `basecolormap*`，可它显示的是 Emit Map，结果四项“对不上”全是测试自己的错。

## 11b. 测试（`tests/m1_tests.py`）

建 7 个球（每个一种材质情况）+ 地面，按帧延时依次检查，全部用数值判定（读 G-Buffer / 输出的像素）：

| 检查 | 判定方法 |
|---|---|
| 加载后自动 Refresh、无报错、着色器全部编译通过 | `status`、`errors()`、Info DAT |
| 法线贴图 | G-Buffer 法线与解析球面法线的平均夹角：有贴图 > 3°，无贴图 < 1.5° |
| 自发光贴图、Channel Source、Phong / Constant / 无材质 / 自定义材质 | 对应球区域内 G-Buffer 的平均值 |
| 三种视角设置方式、改分辨率 | 用深度输出 + 相机基向量重建世界坐标，与 G-Buffer 位置（加回相机位置）的最大误差 < 0.01（16 位 G-Buffer 下实测约 0.006） |
| uniform 数组 | `uniforms` 是 4 通道 × 44 采样（0.7.5 前 40） |
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
| `TEST.M4` 光追 | 代理 > 100 个三角形、两个 GLSL POP 无错、探针每个方向 3–40 个、总数 1000–4096（`EXT.RTGRIDDIMS`，0.7.4 前写死 16×8×16）且有效比例 30%–100%、反射有命中、合成无 NaN、`uRT` 两个开关为 1、Switch 在光追分支；两个调试画面有内容；关闭后 Switch 回到常量 |
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

## 11b-5. 0.8.0 次表面散射测试（`tests/m8_tests.py`）

18 项：版本、uniform 数组 4 × 68；没有 SSS 槽时旁路（composite 1 张缓冲、`sss_src` 在 composite、无报错）；两个槽（Jade、Skin）预设生效、2 张缓冲、`sss_src` 打开；G-Buffer RT3.a 和 composite 第 2 输出里有档案编号；**同一帧里比较 composite（之前）和 `sss_v`（之后）**：无 NaN、非 SSS 像素完全不变（不漏光）、SSS 像素有变化、能量误差 < 3%（实测 0.07%）、皮肤上 95 分位梯度变小（0.0073 → 0.0024）、红通道变化比蓝通道大；GPU `sss_h` + `sss_v` < 0.5 ms；透射：背光的 1 cm 板比 8 cm 板亮（0.027 vs 0.0008）、背光树叶 > 0、正面光照下 ≈ 0；三个 Debug View 无报错；关掉 Subsurface 后旁路。0.8.0：全过。`tests/m8_showcase.py` 出对比图（玉佛、白玉镂空牌，需要 `MODELS` 指向模型文件夹）。

## 11b-6. 0.8.3 贴图坐标和场景比例测试（`tests/m83_tests.py`）

- **贴图坐标**：一张“颜色 = 自己的 UV”的 GLSL TOP 贴图，方盒的 uv[1] 用 Texture SOP 设成 uv[0] × 2.5。BTDR 用它当 Base Color Map（sRGB 关、TAA 关），读 G-Buffer RT0；原生 Render TOP 画同一个方盒，同一张贴图当 Emit Map、不开灯，输出就是贴图。跳过 UV 接缝处的像素后逐像素比较，五种情况（uv0、uv1、uv1 + Extend Hold、uv1 + Extend Mirror、Screen Space）中位误差都是 0.001。另查镜像材质的 `uUV0 / uUV1 / uScr`、采样器 Extend 跟着材质变。
- **场景比例**：同一场景（地面、球、金属方块；AO、反弹光、SSR、雾、Height-Field AO、景深、光追全开）建两份，一份按米，一份所有长度 × 100、Scene Unit = Centimeters。150 帧后最终画面平均差 0.0013（验收线 0.01），再逐个比较 Depth / SSAO / SSGI / SSR / Probe GI / Traced Reflections / Direct Light 的 Debug View，都小于 0.003。
- 0.8.3：18 项全过。Meters 下示例场景和 0.8.2 的 A/B 差值为 0（`ab_compare.py`）。

## 11c. 开发者流程

都在 Textport（Alt+T）里执行，结果写 `btdr/out/`，第一行是 `STATUS ...`：

| 步骤 | 命令 | 结果 |
|---|---|---|
| 构建 | `exec(open(project.folder + '/btdr/build.py', encoding='utf-8').read())` | `release/BTDR.tox`，并复制到 Palette（`BUILD.PALETTE`）；`out/build_log.txt` |
| 替换工程里的实例 | `tools/hotswap.py`（`HOTSWAP_TARGETS` 指定多个，`HOTSWAP_NOBUILD` 跳过构建） | 参数和连线保留 |
| 回归测试 | `tests/m1_tests.py` | 约 20 秒，39 项；测试网络自动删除 |
| 0.8.1 专项 | `tests/m81_tests.py` | 8 项：POP 贴图、薄壁按距离模糊、圆盘旋转逐帧变化、边缘无暗带、薄壁透射提亮 |
| 0.8.3 专项 | `tests/m83_tests.py` | 18 项，§11b-6：贴图坐标和原生逐像素对比、场景比例 |
| 透明测试 | `tests/m6_tests.py`（测试场景单独搭：`tests/m6_scene.py`，`M6_SHOT = 'tag'` 存 `out/m6_<tag>.jpg`） | §11b-3 |
| 混合透明测试 | `tests/m6b_tests.py`（场景：`tests/m6b_scene.py`，`M6_SHOT` 存 `out/m6b_<tag>.jpg`） | §11b-4 |
| 原生用法测试 | `tests/m7_tests.py` | 13 项：空网络封面 / 等待相机、Info 页、场景自动识别、Render 标志、嵌套、线条不破坏光追、Constant MAT 纯色、透明背景对比原生、换材质 / Ambient Light 自动跟上、删相机无报错、Environment Light、封面开关、暂停时拖入；约 6 秒 |
| 演示场景 | `examples/demo_scene.py` | `/project1/btdr_demo`：测试模型 AntiqueCamera + FlightHelmet（`测试模型/`，CC0）、HDRI（Rotate −96.2 对齐 light1）、原生 Render TOP 对照 `native_render`；贴图在 `/project1/tex_lib`。素材说明见 `DEMO_ASSETS.md` |
| 发布用示例 | `examples/make_example.py` | `/project1/btdr_example`，存 `examples/` 和 `release/` 的 `BTDR_Example.tox`（`EXAMPLE.*`） |
| 验收 | `tests/m5_acceptance.py` | §11b-2 |
| 画面 A/B | `tools/ab_compare.py`（先把旧构建复制成 `release/BTDR_ref.tox`） | `out/ab_compare.txt`、`out/ab_A.jpg` / `ab_B.jpg`；性能类改动要求最终画面看不出差别 |
| 展示工程 | 在目标工程（它的文件夹就是包）里：`SHOW_SRC = '<源码>/btdr'`，再 exec `<源码>/btdr/examples/make_showcase.py` | 拷入 BTDR.tox、BTDR_Example.tox、`Image/` 下的 HDRI、USER_GUIDE.md、README.txt，建 `/project1/showcase`（4 个预设：Studio / HDRI / Volumetric Fog / Night，`SHOWCASE.*`）；HDRI 用相对路径，整个文件夹可以搬走。2026-11-12 生成了 `F:/Projects/Touchdesigner Projects/BetterTDRender/BetterTDRender.toe` |
| 加密发布用的壳 | `tools/make_shell.py`（在 `build.py` 之后） | `release/BTDR_Shell.tox`，并复制到 Palette；`out/shell_log.txt` |
| 打包 | `tools/make_release.py` | `release/BTDR_<版本>.zip`：BTDR.tox、BTDR_Example.tox、USER_GUIDE.md、README.txt（源文件 `docs/RELEASE_README.txt`）、`hdri/`；`out/release_log.txt` 列出每个文件的 md5 |

发布顺序：构建 → 回归测试 → 示例 → 验收 → 打包。

**版本备份（`BUILD.BACKUP`，0.8.0 起的规则）**：每次发布都另存一份文件名带版本号的 tox，以后的版本不覆盖它。`build.py` / `make_example.py` / `make_shell.py` 自动写 `release/versions/BTDR_<版本>.tox`、`BTDR_Example_<版本>.tox`、`BTDR_Shell_<版本>.tox`（提交进 git），并复制到 Palette 的 `BTDR` 文件夹；不带版本号的 `BTDR.tox` 等仍是“最新版”。0.7.5、0.7.6 的备份从 git 历史里补齐。0.8.3 起 `release/versions/RELEASED.txt` 列出已发布的版本，这些版本号的备份不再被覆盖（§11 第 59 条）：开始开发新版本时先改 `VERSION`，发布时把它加进 `RELEASED.txt`。案例场景另存为 `examples/BTDR_SSS_Case.tox` 和 `BTDR_SSS_Case_<版本>.tox`（模型按绝对路径引用 `ue5/模型_简化`，不在 tox 里）。

示例网络（`EXAMPLE.*`）的取舍：只用 TD 自带的 SOP 和原生 PBR MAT，不带任何外部文件；相机在场景前方 ±55° 摆动（转到墙后面会看到墙背面）；灯的原生阴影关掉；Bloom 0.15 让发光方块有光晕；`keep_cooking`（帧开始时拉取 OUT）存盘前关掉，用户打开时按需计算。

## 12. 尚未实现

- M5 遗留：示例网络的 4060 / 2060 实测；Palette 安装说明以外的安装方式（TD 的 Package / 组件库）。
- M4 遗留：实例化几何体进光追代理；命中点用逐纹素的贴图颜色（现在是每物体平均色）和高光；探针可见性（DDGI 的深度矩，防薄墙漏光）；光追阴影；探针多次反弹；不支持光追的机器上实测降级路径。
- M3 遗留：High 档 SSGI 半分辨率 + 深度感知上采样；雾里的局部光源；屏幕空间光束（太阳在画面里时的径向光芒，便宜的补充）。
- M2 遗留：物体运动矢量（物体自身运动的运动模糊、TAA 更少拖影）、景深的散景形状（目前是圆盘）、镜头切换的自动检测（现在只在换相机节点时重置历史）。
- M6 遗留：M6a 剩余项见 §9e 末尾；M6b 混合透明默认不构建（§9f 写了要改进的地方）；M6c：命中点用贴图颜色、色散、光追玻璃投彩色阴影（焦散）。
- 0.8 遗留（次表面散射，`docs/SUBSURFACE.md`）：可选的厚度贴图（Thickness Map）、多光源的透射、光追反射 / 探针里的 SSS 物体不散射、半分辨率的 Low 档。
- 0.8.3 遗留：三平面投影（原生本身不起作用，§11 第 58 条；需要时可以自己实现）、POP 的自定义贴图坐标属性、一个材质里第三套 UV、实例纹理坐标（Instance Texture）。光追折射在 m6 的 M6c 两项测试里经常第一次就失败（0.8.2 同样，数值完全相同），要查 `rt_refr` 首帧读数的时机。m83 的场景比例场景（`docs/images/sceneunit_compare.jpg`）里，金属方块顶边和球旁的光滑地面上有方格状暗斑，米 / 厘米两边一样，疑似 1/4 分辨率光追反射的放大，待查。
- 之后：多盏灯、点光 / 聚光、正交相机、点精灵（未实测）。嵌套几何体、场景变化自动检测已在 0.7.4 / 0.7.5 完成；仍需手动 Refresh 的只剩“改了材质颜色后让光追代理的平均色跟上”。

## 13. 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-11-11 | — | M0 技术验证，方案第 3 版（单节点 + 原生 PBR MAT + 场景镜像），见 `archive/ue5r/docs/TOOLKIT_PLAN.md` |
| 2026-11-19 | 0.8.3 | 贴图坐标和场景比例（`ROADMAP_0.9.md` §3）。**贴图坐标**（`GBUF.UVSET` / `EXT.UVSET` / `EXT.SAMPLERSTATE`）：镜像材质每张贴图的 Extend U / V、Filter 用表达式绑到 PBR MAT（各向异性取材质的、最低 4×）；新增 `uUV0` / `uUV1`（每张贴图的代码 = UV 套 + 2 × 屏幕空间，`uUV1.w` = 额外那套 UV 的编号）和 `uScr`（1 / 分辨率），`gbuffer.vert` 多传一套 `texCoord1 = TDTexAttrib_Tex(uUV1.w)`，`gbuffer.frag` 的 `uvOf()` 按代码取 uv0 / uv1 / 屏幕坐标，法线贴图的切线框架用它自己的坐标。Triplanar 不支持（§11 第 58 条），用了会提示。和原生逐像素一致（§11b-6）。**场景比例**（`BUILD.SCENEUNIT` / `UNI.UNIT`）：Render 页 Scene Unit（Meters / Centimeters / Millimeters / Inches / Feet / Custom + Unit Size）；`uniforms` 算 K = 每米多少场景单位，写进 `uB[42]`（`uUnit`），按米设计的参数乘 K（AO / GI 半径、SSR 距离和厚度、雾的浓度 / 衰减 ÷ K、基准高度和距离 × K、HF AO 半径、散射半径、薄片厚度），景深在米里算（对焦距离 × 米每单位，`dof.frag` 把深度换成米），吸收距离在 `refract` / `rt_refr` 里用 `UM()`；着色器里按米写死的常数都包上 `UM()`（阴影 / 雾的偏移和 PCSS 搜索范围、SSR / 光追的起点偏移、光追反射的最远距离、SSS 透射的偏移和薄片衰减、折射步进起点、雾的噪声频率），探针网格的边距也乘 K。改 Scene Unit 自动 Refresh。**备份保护**：`RELEASED.txt`（§11 第 59 条）。新测试 `tests/m83_tests.py` 18 项；回归 m1 39、m81 8、m8 18、m7 13、m5 7 全过；m6 除 M6c 两项外全过（0.8.2 同样失败，§12）。Meters 下和 0.8.2 的 A/B 差 0 |
| 2026-11-19 | 0.8.2 | 内部网络重新排版（`ANNOT.LAYOUT`，`ext/annotations.py` 的 `layout()`）：只改节点的 nodeX / nodeY，不增删节点、不改连线和参数（构建前后 199 条连线逐条比对一致）。GROUPS 改成 20 组、按一帧的数据流排序，每项多了“每行几个”；组内排成网格，组与组像书架一样从左到右排，一排超过 4400 换行；组宽至少等于标题宽，标题不会压到隔壁。没写进 GROUPS 的新节点会自动放进“其他”组并记进构建日志。结果：20 个分组框，0 个跳过（0.8.1 只有 4 个）。m81 / m8 的版本检查改成读 build.py 的 VERSION。回归 m81 8、m8 18、m1 39 全过 |
| 2026-11-19 | 0.8.1 | 把皮肤鼓包委托（2026-11-16）里改在工程副本上的修复并回仓库，并做成通用的：① **POP 贴图坐标**（`GBUF.POPUV`）：镜像材质声明 `Tex` 属性，`gbuffer.vert` 用 `TDTexAttrib_Tex(0)`（SOP 上等于 `uv[0]`）；以前 POP 上 `TDTexCoord(0)` 是 0，所有贴图只采到一个角。② **薄壁磨砂按距离模糊**（`REFR.DIFFUSE`）：模糊宽度 = (到背后表面的距离 + 1 cm) × 粗糙度² × 2，换算成那个表面处的像素；以前薄壁只按粗糙度模糊，远近一样。③ **平滑模糊**（`REFR.SMOOTHBLUR`）：精细一级 mip 上的 12 点旋转圆盘代替直接读盒式 mip（方块感）；旋转用逐帧变化的交错梯度噪声（Jimenez 2014），委托里的版本用固定的逐像素哈希，留下一层静态的淡斜纹。④ **边缘**（`REFR.EDGE`）：只有最外几像素淡到环境（以前 5%）；圆盘采样坐标限制在画面内——画面外的采样读到黑色才是磨砂表面边缘暗带的真正原因。⑤ **薄壁透射提亮**（`REFR.THINTINT`）：透明槽新增 Thin Transmission Lift（默认 0，等于以前），编码进 `uTrans.w`（0 实心，1 + 提亮 = 薄壁），写到透明层 RT4.w。委托里的 `REFR.LENS`（薄膜鼓包当凸透镜，写死了朝上方向和强度）没有并入，留作以后的通用 Refraction Scale。⑥ **内部注释**（`BUILD.ANNOT`，`ext/annotations.py`）：186 个节点的 Comment、总览面板、4 个分组框（其余分组的节点交错摆放，不挪节点就框不干净，构建日志列出跳过的组；0.8.2 重新排版后 20 组全部画出）。新测试 `tests/m81_tests.py` 8 项；回归 m1 39、m6、m7 13、m8 18、m5 7 全过（m6 的光追首帧偶发一次，§11 第 43 条） |
| 2026-11-14 | 0.8.0 | 次表面散射（方案 `docs/SUBSURFACE.md`）：Subsurface 页 + SSS 槽（序列参数，拖入 Geometry COMP，最多 8 个档案，8 个预设 Skin / Jade / Wax / Marble / Milk / Soap / Leaf / Paper，`EXT.SSSPRESET`）。档案编号写进不透明 G-Buffer 的 RT3.a（= 2 + k，`GBUF.SSSID`；不透明层本来不读这个通道），不加缓冲；材质里是静态的 `uSSS`。composite 在有 SSS 物体时多一个输出：不乘底色的辐照度 × 底色^(1 − Texture Detail) | 档案（`COMP.SSS`，太阳 / 环境的辐照度由 `lightingTerms` 留在全局变量 `gSunIrr` / `gEnvIrr`，`LIGHT.SSSIRR`）。`sss_h` / `sss_v`：可分离的屏幕空间散射（Jimenez 结构 + 每通道两个指数的 Burley 型曲线，按 (i/N)² 布点，跨档案或深度差超过半径时取中心值，能量守恒，最大 64 像素，`SSS.*`），`sss_v` 只改漫反射部分。透射（`COMP.SSSTRANS`）：厚度 = 到阴影相机的距离 − 阴影图深度（4 点平均），exp(−厚度 / 每通道散射距离) × 0.5；薄片模式用固定厚度并透过背面环境光。uniform 数组 44 → 68（41 全局，44 + 3k 档案）。Debug View 新增 3 项（`DEBUG.SSS`，用 Switch 挡住不存在的缓冲）。没有 SSS 物体时全部旁路。新测试 `tests/m8_tests.py` 18 项全过。实测（1080p，SSS 约占画面 1/4–1/3）：GPU `sss_h` + `sss_v` 约 0.1–0.13 ms，composite +0.04 ms；CPU 约 +0.1 ms |
| 2026-11-13 | 0.7.6 | 加密发布用的壳（`EXT.SHELL`，`tools/make_shell.py` → `release/BTDR_Shell.tox`）：用户给 `renderBTDR` 加 TD Privacy 后节点预览为空（`opviewer` 指向的内部 `out1` 从外面访问不到，渲染和输出口都正常）。壳 = 公开的 Base COMP（标签 `BTDRshell`）：`copyParameters` 复制全部自定义参数页（含序列），三个 Out TOP 接 `core` 的输出口，`opviewer` 指向壳里的 `out1`；`core` 的参数绑定到壳上（`SyncShell`：普通参数 bind，双向，Status / Quality 写回都能看到；OP 类参数用表达式 `parent().par.X.eval()`，相对路径按壳所在网络解析；序列块数每次 Refresh / `scene_watch` 时对齐并补绑），`_find` 以壳的父网络为基准；脉冲不经过绑定，由壳里的 `shell_pulse` 转发。实测：改 Geometry、Quality、加透明槽、按 Refresh Scene 都生效，无报错。`make_example.py` 同时更新 Palette 里的示例 |
| 2026-11-13 | 0.7.5 | “和原生 Render TOP 一样用”（和原生并排对比后列出的问题，新测试 `tests/m7_tests.py` 13 项）：① 时间轴暂停时拖入不再卡在加载封面：`execute` 里同步 Refresh（延时调用只做后备），暂停时跳过预热直接出画面（`EXT.PAUSED`；用户机器上暂停时帧完全不推进，`run(delayFrames)` 永远不触发）；`scene_watch` 改用 `absTime.frame`。② 删掉相机不再留下红色错误：`cam_jit` 的表达式在相机不存在时退回默认值（`EXT.CAMGONE`）。③ 跟随 Geometry COMP 的 Render 标志、画嵌套的 Geometry COMP（`EXT.GEOS`）。④ Background 新增 Transparent：`grade` 用 HDR alpha 里的稳定深度和 3×3 邻域最近深度算覆盖率，预乘输出（`GRADE.ALPHA`，`uEnv.z = -1`）；和原生的 alpha 平均值差 0.0004。⑤ Constant MAT 不受光（`EXT.UNLIT` / `GBUF.UNLIT`：颜色走自发光，base 0 + metallic 1 + roughness 1 + AO 0 让所有光照项为 0，不占 G-Buffer 通道）；Tone Mapping = None 时红色实测 (1, 0, 0)。⑥ Vignette、Grain 默认 0。⑦ 弹窗每个工程只弹一次（`EXT.INFOONCE`，Info 页 Show At Startup 弹过后自动关）；Info 页 Cover While Loading 可关封面。⑧ `scene_watch` 的签名加上 Render 标志、材质路径、带 Render 标志的 SOP / POP：换材质节点、换 SOP 自动刷新（`EXT.WATCH`）。⑨ Ambient Light COMP：颜色 × Dimmer 加到漫反射环境项（`EXT.AMBIENT` / `UNI.AMBIENT` / `COMP.AMBIENT`）；uniform 数组 40 → 44 槽（`uAmb` = 40，41–43 空闲）。⑩ 开放曲线不进光追代理（`EXT.RTLINES`：一条 Line SOP 曾让整个场景的 `rt_refl` / `rt_probes` 报错）|
| 2026-11-13 | 0.7.4 | 封面和加载画面（`BUILD.COVER` / `EXT.COVER`，`shaders/cover.frag`）：第 1 个输出在找到相机、渲染预热 60 帧之前显示 TD学长 的 Logo（有向距离场绘制，tox 里没有图片文件；加载时扫光、等待相机时三个小条慢闪），`out_src` 只拉取选中的一支，渲染画面出来后封面不计算；加载期间 `cover_warm` 每帧拉取 `view` 让着色器编译、时间累积填满。没有相机时每 30 帧查一次 Camera 参数（`CoverPoll`），相机出现就自动刷新。只在启动 / 新建后出现一次（`warmed` 不存盘）。About 页改为 Info 页：版本、作者、微信、闲鱼、两个邮箱、许可、源码和 About / Contact... 按钮；每次 TD 运行第一次加载时弹出作者和联系方式（`EXT.INFO`，`op.TDResources.PopDialog`，同一次运行只弹一次）。`TEST.M4` 的探针数检查改成按 `EXT.RTGRIDDIMS` 的规则（0.7.3 起不再是 16×8×16）。修复（用户在新工程里发现）：先拖入 BTDR、后建几何体时场景一直是空的，空的光追场景让 `rt_refl` / `rt_probes` 编译失败、`rtscene/merge` 没有输入，节点上一串红色错误。现在 `scene_watch` 每 30 帧比较一次 Camera / Geometry / Lights 解析出的路径，有变化就自动 Refresh（`EXT.WATCH`，取代只等相机的轮询）；光追代理为空时 Ray Tracing Available 为关，光追节点不被拉取（`EXT.RTEMPTY`）。环境：Source 新增 Auto 并设为默认（`BUILD.ENVAUTO` / `EXT.ENVLIGHT` / `UNI.ENVAUTO`），和原生 Render TOP 一样读 Lights 匹配到的 Environment Light COMP（贴图、Dimmer、Rotate Y）；以前用户放了 Environment Light COMP，金属球却只反射内置摄影棚。和原生对比：太阳、云的方位一致；原生不算遮挡，球下半部分映出被地面挡住的海面，BTDR 映出地面 |
| 2026-11-13 | 0.7.3 | 许可从 MIT 改为 PolyForm Noncommercial 1.0.0（禁止商用；再分发必须保留 `LICENSE` 首行的 `Required Notice:` 出处声明）。README、THIRD_PARTY_NOTICES、使用手册 §9、介绍视频片尾同步 |
| 2026-11-13 | 0.7.3 | 粒子示例（`examples/swirl.comp`）：沙子悬在镜面上方 15 cm（`CH_Y 0.15`），换图形时弹跳、横向抖动（`act = sin(π·s)`），落定后只随低音轻颤；扩散收窄（0.004+0.008·bass）。镜面倒影用平面镜像（`SCENES.MIRROR`）：同一组实例 sy = −1 + 暗一档的材质，渲染器的 Geometry 不含地面——屏幕空间反射分辨不出几毫米的沙粒，只能得到竖向拉丝（实例化几何体也还不进光追，§12）。介绍视频 v4：剪辑点全部落在 120 bpm 的小节线上，音乐（`tools/video` 外的 music3）按实测的画面事件写 |
| 2026-11-12 | 0.7.3 | 雾里的太阳阴影改用和表面相同的 PCSS（`FOG.SHADOW`）：8 个遮挡搜索 + 12 个 PCF 采样，每格每帧随机旋转，半影随到遮挡物的距离变大；Fog Shadow Blur 改为“相对表面阴影的半影倍数”（1 = 一致，0 = 单点硬阴影）。原因：0.7.2 的固定 3×3 小核让百叶后的每层光片几米外仍是硬边，从斜角看就是一道道斜条纹，而地面上同样的影子是软的（多机位 + CPU 参考图对比，见 §11 #47）。深度方向的抖动始终取满整片（Fog Jitter 只缩放屏幕方向，`FOG.JITTER`）：只抖半片时百叶光片和深度切片产生摩尔纹，表现为横穿光束、和光方向无关的斜带（§11 #49）。帧号取模 4096（`UNI.FRAMEWRAP`，§11 #48）。探针 GI：探针数按场景包围盒的形状分配，三个方向间距大致相同（约 2048 个，`EXT.RTGRIDDIMS`；以前固定 16×8×16，又宽又浅的场景深度方向只有 0.1 m 间距，相邻层探针的噪声在平面上变成彩色条纹）；查表时表面背后的探针权重接近 0、查表点沿法线偏移 0.3 倍间距（`GI.PROBE_SAMPLE`，以前背后的探针仍有 0.2 权重，漏光）。百叶窗场景 Fog Shadow Blur 2.5 → 1。High 下 `fog_scatter` 0.16 → 0.27 ms |
| 2026-11-12 | 0.1.0–0.7.2 | 见 `CHANGELOG_EARLY.md`（M1 核心出图 … M6 透明与折射、光追折射、实例颜色、雾的噪声控制） |
