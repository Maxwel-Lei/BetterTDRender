# BetterTDRender（BTDR）早期变更记录（0.1.0–0.4.0）

从 `IMPLEMENTATION_2.md` §13 移出（2026-11-19，0.8.2），那份文档超过了一次能读完的长度。0.3.5 及以后的记录仍在 §13。

| 日期 | 版本 | 变更 |
|---|---|---|
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
