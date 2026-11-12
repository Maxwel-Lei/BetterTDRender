# BetterTDRender（BTDR）实现参考

面向维护者（包括之后接手的 AI）。每一节对应源码里的锚点：在 `btdr/` 里搜索 `[BTDR:锚点名]` 就能定位到实现位置。
使用方法见 `USER_GUIDE.md`。旧管线 `ue5r/` 已归档到工程目录的 `archive/ue5r/`（实现参考在 `archive/ue5r/docs/IMPLEMENTATION.md`；M2–M4 已全部移植，见 §9b–§9d；`archive/README.txt` 说明归档内容）。

## 0. 维护规则

- **锚点**：源码注释里的 `[BTDR:XXX.YYY]`。改名、移动、删除实现时同步改本文件；新增重要逻辑时新增锚点并在这里登记。
- **每个文件第一行**有 `[BTDR:FILE.XXX]`。
- **源码是文件，`.tox` 是产物**：只改 `btdr/shaders/` 和 `btdr/ext/`，然后跑 `build.py`。不要直接改 `.tox` 里的节点。
- **改完必须验证**：`tests/m1_tests.py` → `out/m1_tests.txt` 第一行 `STATUS PASS`；`build.py` → `out/build_log.txt` 第一行 `STATUS DONE`；`examples/demo_scene.py` → `out/demo_log.txt` 第一行 `STATUS DONE` 且没有 `ERR` / `--- compile` 行；看 `out/demo.jpg`。发布前再跑 `examples/make_example.py`（重新生成 `BTDR_Example.tox`）和 `tests/m5_acceptance.py`（`out/m5_acceptance.txt` 第一行 `STATUS PASS`）。开发者流程（构建、测试、示例、发布打包）见 §11c。
- **文档跟着代码走**：行为、默认值、限制有变化时，同一轮里更新 `USER_GUIDE.md` 和本文件，并在 `IMPLEMENTATION_2.md` 的"变更记录"加一行。
- **本文件分两份**（单个文件太长，读取会被截断）：本文件是 §0–§9d（结构和各 pass 的算法）；`IMPLEMENTATION_2.md` 是 §10–§13（性能、已知的坑、测试、尚未实现、变更记录）。两份的章节号连续，引用 "§11" 等指的是第 2 份。
- 提交文件到设备时，同一个本地暂存路径重复提交有时不生效；每次用新的暂存文件名（放在 `btdr/stage/`）。

## 1. 文件结构

```
btdr/
  build.py                构建脚本：生成 release/BTDR.tox
  shaders/                GLSL。common.glsl 会被拼到每个着色器前面（材质着色器 gbuffer.* / shadow.* 除外）；*.comp 是计算着色器
  ext/BTDRExt.py          扩展类：解析场景、建镜像、阴影相机
  ext/uniforms_chop.py    Script CHOP 回调：每帧填共享 uniform 数组
  ext/parexec.py          参数变化 → 调扩展
  ext/execute.py          组件创建 / 工程启动时自动 Refresh
  examples/demo_scene.py  开发用的演示场景 /project1/btdr_demo（测试模型 + HDRI）+ 验证（报错收集、截图、耗时）
  examples/make_example.py  生成发布用的示例网络 BTDR_Example.tox（只用 TD 自带 SOP，§11c）
  tests/m1_tests.py       回归测试：39 项检查（M1–M4），结果写 out/m1_tests.txt
  tests/m5_acceptance.py  验收：按使用手册 §2.2 从空网络搭场景 + 示例冷启动检查，结果写 out/m5_acceptance.txt
  tools/make_release.py   打发布包 release/BTDR_<版本>.zip（§11c）
  tools/perf_bench.py     性能测量（逐渲染器），结果写 out/perf_bench.txt
  tools/cpu_profile.py    单个 renderBTDR 的逐节点 CPU / GPU 耗时（只列每帧都计算的节点，PROF.STEADY），结果写 out/cpu_profile.txt
  tools/shots.py          示例场景固定机位截图（前后对比用），写 out/shot_<标签>_<机位>.jpg
  tools/hotswap.py        重建 tox 并替换示例场景里的 renderBTDR1，保留全部参数和连线（HOTSWAP_TARGETS 可指定其他实例）
  tools/variants.py       同一机位下切换几组参数各截一张图（VARIANTS / VAR_CAM / VAR_ORBIT），写 out/var_<标签>.jpg，结束后恢复参数和相机。
                          机位：wide、helmet、camera、floor（贴地看物体脚部：AO、倒影）、sun（逆光穿过物体：雾里的光束）
  tools/gltf2obj.py       glTF / GLB → 每个材质一个 OBJ（世界坐标，合并所有实例）+ 拆开的 PBR 贴图（ORM 拆成 ao / roughness / metallic）
  tools/model_preview.py  把 测试模型/<名字> 载入 /project1/btdr_models/<名字>（PBR MAT、HDRI、地面、renderBTDR），存 out/preview_<名字>.jpg
  tools/normal_convention_test.py  判断法线贴图是 OpenGL 还是 DirectX 约定（会加载原始高模，只能在空工程里跑）
  tools/ab_compare.py     两个构建在同一场景上逐像素比较（示例网络载入两份，A 用当前构建，B 用 release/BTDR_ref.tox），写 out/ab_compare.txt；同一个构建自比差为 0
  tools/apply_stage.py    按清单（stage/manifest_*.txt：目标、暂存名、md5）校验后把暂存文件复制到位（§0 的暂存规则）
  m4/rt_spike.py          M4 技术验证：从一组 Geometry COMP 实时建光追场景、测加速结构重建开销
  release/                产物：BTDR.tox、BTDR_Example.tox、BTDR_<版本>.zip
  docs/                   本文档（IMPLEMENTATION.md + IMPLEMENTATION_2.md）、使用手册、PERF_HISTORY.md（历次性能实测）、DEMO_ASSETS.md（示例场景和测试素材）
  out/                    构建日志、示例日志、截图
  m0/                     M0 技术验证脚本和结果
```

## 2. 组件内部结构

`renderBTDR` 是一个 Base COMP（Parent Shortcut = `BTDR`，内部用 `parent.BTDR` 引用），内部节点：

```
uniforms (Script CHOP) ──▶ 所有 GLSL TOP 的 uB[40]；每帧把 TAA 抖动写进 cam_jit 的 Window X / Y
cam_jit (Camera COMP, 父物体 = 用户相机, 镜头参数用表达式跟随) ──▶ gbuffer 的相机

scene/  g0..gN (镜像 Geometry COMP)   m0..mK (G-Buffer GLSL MAT)
   │
   ├─▶ gbuffer (Render TOP, 相机 cam_jit, 4 个颜色缓冲) ─▶ gbuf0..3
   └─▶ shadow  (Render TOP, 相机 suncam, 覆盖材质 mat_shadow) ─▶ shadow_cache (Cache) ─┐
                                                       shadow ─────────────────────┴▶ shadow_src (Switch)
env_studio ─┐
env_user  ──┴▶ env_src (Switch) ─▶ env_atlas (3D, 预滤波)

gbuf0..3 + shadow_src + env_src + env_atlas ─▶ lighting (4 个输出) ─▶ lit1..3   （0.5.1 起只有 debug 读，见 COMP.INLINE）
gbuf1 + gbuf2 + taa_hist ─▶ ssgi ─▶ ssgi_acc ◀─ ssgi_hist (Feedback) ─┐ ssgi_src (Switch: 常量 / ssgi_acc)
gbuf1 + gbuf2 + taa_hist ─▶ ssr  ─▶ ssr_acc  ◀─ ssr_hist  (Feedback) ─┘ ssr_src  (Switch: 常量 / ssr_acc)
gbuf0..3 + shadow_src + env_src + ssgi_src + ssr_src + hf_src + rt_src + env_atlas + probe_src0..3 ─▶ composite（光照项在这里现算）
shadow_src + env_src + env_atlas ─▶ fog_scatter (3D 计算) ─▶ fog_accum (3D 计算) ◀─ fog_hist (Feedback, Target TOP = fog_accum)
fog_accum ─▶ fog_integrate (3D 计算)
composite + gbuf2 + fog_integrate ─▶ fog_apply;  fog_src (Switch: composite / fog_apply)
fog_src ─▶ taa ◀─ taa_hist (Feedback, Target TOP = taa, 输入接 gbuf0 只用来定尺寸)
taa ─▶ post_dof (Switch: taa / dof) ─▶ post_mb (Switch: 上一级 / mblur) ═▶ out2 (HDR，alpha = 视深)
post_mb ─▶ bloom_pre (½) ─▶ bloom_d1 (¼) ─▶ … ─▶ bloom_d6 (1/128) ─▶ bloom_u5 ─▶ … ─▶ bloom_u0 (½)；bloom_src (Switch: bloom_off / bloom_u0)
post_mb ─▶ ae_lum (256×144) ─▶ ae_avg (Analyze, 平均) ─▶ ae_exposure (1×1) ◀─ ae_hist (Feedback)；ae_src (Switch: ae_off / ae_exposure)
[post_mb, bloom_src, ae_src] ─▶ grade ─┐
gbuf* + lit* + ssgi_src + ssr_src ─▶ debug ──────────┴▶ view (Switch) ─▶ out1
gbuf1 + gbuf2 ─▶ depth ─▶ out3

M4（§9d）：
rtscene/  每个几何体：Select → Convert → PolyReduce → SOP to POP → Transform POP (矩阵表 xf<i>) → ObjId ─▶ merge ─▶ tri ─▶ out
rt_scene (Select POP = rtscene/out) ═▶ 加速结构（GLSL POP 的 Collisions 页）
rt_probe_grid ─▶ rt_probes (GLSL POP, uB 来自 rt_static) ─▶ probe_sh0..3 (POP to TOP, 3D) ─▶ probe_src0..3 (Switch: rt_probe_off / probe_sh)
rt_refl_grid ─▶ rt_refl (GLSL POP, 每帧) ─▶ rt_refl_top ─▶ rt_acc ◀─ rt_hist (Feedback) ─▶ rt_src (Switch: rt_off / rt_acc)
rt_mat / rt_static (Table DAT) ─▶ rt_mat_chop / rt_static_chop (DAT to CHOP)
composite 接 rt_src（2D 第 9 个）和 probe_src0..3（3D 1–4）；debug 接 rt_src（2D 第 10 个）和 probe_src0..3（3D 0–3）
```

坐标与约定（和旧管线一致）：
- 全部光照在**世界空间**做。G-Buffer 是 `rgba16float`，位置存的是**相对相机**的坐标（`GBUF.RELPOS`），读的时候加回 `uCamPos`。
  16 位浮点有效位约 3 位十进制：离相机 5 m 处误差约 4 mm，离得越近越准，正好是画面最需要精度的地方。
- HDR 线性色彩；只有 `grade` 输出 sRGB 8 位。
- 相机不用矩阵，用 4 个 vec4：位置、右、上、前（`.w` = tan(水平视角/2)）。
- 环境辐照度已含 1/π，直接乘漫反射颜色。

## 3. 构建脚本 `build.py`

| 锚点 | 内容 |
|---|---|
| `BUILD.SHADER` | 读着色器：前面拼 `common.glsl`；`//#include x` 一行替换成 `shaders/x.glsl` 的内容 |
| `BUILD.PARS` | 全部自定义参数页（Render / Light / Environment / Grade / About） |
| `BUILD.UARRAY` | 给 GLSL TOP 挂上共享 uniform 数组 `uB` |
| `BUILD.UNIFORMS` | `uniforms` Script CHOP |
| `BUILD.UNICOOK` | `uniforms` 上的自定义参数 `Frame`，表达式 `absTime.frame`：让它每帧计算（见 §11 第 23 条） |
| `BUILD.GBUF` | G-Buffer Render TOP：几何体模式 `scene/g*`，4 个颜色缓冲，不开 MSAA |
| `BUILD.SHADOW` | 阴影：正交相机 `suncam` + 覆盖材质 |
| `BUILD.ENV` | 环境：摄影棚 / 用户 HDRI → 清晰全景 + 预滤波 3D 图集 |
| `BUILD.LIGHT` | 光照 GLSL，4 个输出缓冲。0.5.1 起只给 Debug View 用 |
| `BUILD.GRADE` | 调色、Debug View 切换 |
| `BUILD.OUT` | 三个输出口 |
| `BUILD.TAAPARS` / `BUILD.POSTPARS` | Render 页的抗锯齿参数、Post 页（Bloom、自动曝光、景深、运动模糊） |
| `BUILD.JITCAM` | 内部相机 `cam_jit`（见 `EXT.JITCAM`） |
| `BUILD.TAA` | `taa` + 历史帧 `taa_hist`（Feedback TOP：输入只用来定分辨率，Target TOP = `taa`；把 `taa` 接进它的输入会形成依赖环） |
| `BUILD.POST` | 景深、运动模糊（各用一个 Switch TOP 旁路，关闭时不计算）、Bloom（`BUILD.BLOOM`：6 级 mip 链，强度为 0 时旁路）、自动曝光 |
| `BUILD.AE` | 自动曝光的 1×1 状态（`ae_exposure` + Feedback `ae_hist`） |
| `BUILD.AEOFF` | 0.5.1：自动曝光关闭时 `grade` / `bloom_pre` 经 Switch `ae_src` 读 1×1 常量 `ae_off`（log2 0、倍数 1），测光链不再被拉取（约省 0.1 ms CPU；以前着色器忽略这个输入，但 TD 照样每帧计算整条链） |
| `BUILD.COMPINLINE` | 0.5.1：`composite` 直接接 G-Buffer、阴影、环境，自己算光照项（`COMP.INLINE`）；输入延伸方式 Repeat（环境要绕回） |
| `BUILD.SSPARS` / `BUILD.FOGPARS` | Indirect 页、Fog 页 |
| `BUILD.SS` | 屏幕空间链 `ss_chain()`：噪声 pass → 时间累积（自己的 Feedback 历史）→ Switch（关闭时接中性常量，链上节点不计算）。High 全分辨率、Low 半分辨率 |
| `BUILD.FOG` | 体积雾：三个 3D 计算着色器（`fog_scatter` 和 `fog_accum` 每个格子一个线程，`fog_integrate` 每列一个线程）+ `fog_apply`，Switch 旁路 |
| `BUILD.FOGACC` | 雾的时间累积：`fog_accum` + Feedback `fog_hist`（输入接 `fog_scatter`，Target TOP = `fog_accum`，没有依赖环） |
| `BUILD.PALETTE` | 构建后把 tox 复制到 `~/Documents/Derivative/Palette/BTDR/BTDR.tox`（Palette 面板 My Components）；Palette 文件夹不存在时跳过 |
| `BUILD.HFAO` / `BUILD.HFPARS` | 高度场 AO：朝下的正交相机 `topcam`（中心、范围跟随阴影参数，`tx/ty/tz/orthowidth` 用参数表达式）→ `hf_render`（复用 `mat_shadow` 和阴影的投影物体列表，512² / Low 256²，r32float）→ `hf_cache` → `hf_src`（Switch，关时接常量 `hf_off`）；Indirect 页三个参数 |
| `BUILD.TBUF` | 渲染到 3D 纹理的着色器用纹理缓冲读 uniform（见 §11 第 19 条） |
| `BUILD.RTPARS` | Ray Tracing 页（M4） |
| `BUILD.RT` / `BUILD.RTPROBES` / `BUILD.RTREFL` / `BUILD.RTAS` | M4 光追：`rtscene`、两个 GLSL POP、POP to TOP、Switch、累积；加速结构的构建方式（§9d） |

构建流程：在 `/project1/btdr_build` 里生成 `renderBTDR` → 存成 `release/BTDR.tox` → 复制到 Palette → 删掉构建副本。tox 不引用任何外部文件（已验证：从 Palette 载入后没有 DAT 的 File 参数指向外部）。
注意：脚本新建的 GLSL TOP / GLSL MAT 会自带几个停靠的模板 DAT，`undock()` 把它们删掉，否则会被存进 `.tox`。

## 4. 共享 uniform 数组（`uniforms_chop.py`、`common.glsl`）

`UNI.BLOCK`：Script CHOP `uniforms` 输出 4 通道 × 40 采样，所有 GLSL TOP 把它当作 `uniform vec4 uB[40]` 读（3D 的雾 pass 当作纹理缓冲 `uBbuf` 读，再拷进同名全局数组，`BUILD.TBUF`）（镜像材质不读：材质里没有任何每帧变化的 uniform，见 `EXT.JITCAM`）。
`common.glsl` 里用 `#define uCamPos uB[0]` 这类宏给每个槽位起名字。**改槽位要同时改这两个文件。**

| 槽位 | 宏 | 内容 |
|---|---|---|
| 0–3 | `uCamPos/Right/Up/Fwd` | 当前相机 |
| 4–7 | `uPrevPos/Right/Up/Fwd` | 上一帧相机（TAA 重投影、运动模糊用；都不含抖动） |
| 8 | `uJitter` | xy 当前帧抖动、zw 上一帧抖动（NDC）。只作记录：抖动实际作用在 `cam_jit` 的投影上，TAA 用不含抖动的相机重投影 |
| 9 | `uFrame` | 帧序号、帧时长、历史重置标志、秒 |
| 10–14 | `uSunDir/Color/Pos/Right/Up` | 主光方向和强度、颜色和阴影柔和度、阴影相机位置和开关、右和正交宽度、上和远裁剪 |
| 15–16 | `uEnv`、`uBgColor` | 环境强度 / 旋转 / 背景模式 / 背景模糊；背景颜色和亮度 |
| 17 | `uGrade` | 曝光倍数、暗角、颗粒、色调映射 |
| 18 | `uView` | Debug View 序号、sRGB 开关、距离淡出起止 |
| 19 | `uClip` | 相机近、远、宽高比 |
| 20 | `uTAA` | 当前帧权重、TAA 开关、方差裁剪 γ（1.25） |
| 21 | `uBloom` | 强度、阈值、膝部、半径（mip 链混合比例） |
| 22–23 | `uAE`、`uAE2` | 开关、最小 / 最大 EV、目标灰；变亮速度、变暗速度、帧时长、重置 |
| 24–25 | `uDOF`、`uDOF2` | 焦距 mm、光圈、对焦距离、最大半径 px；传感器宽 mm、开关、采样步长（随 Quality） |
| 26 | `uMB` | 快门、最大拖影 px、采样数（High 12 / Low 6）、开关 |
| 27 | `uSS` | AO 强度、反弹光强度、SSR 强度（0 = 关） |
| 28 | `uGI` | AO / 反弹光半径、步数（High 8 / Low 6）、方向数（High 2 / Low 1） |
| 29 | `uSSR` | 最远距离、步数（High 32 / Low 20）、最大粗糙度、物体厚度 |
| 30 | `uAcc` | 时间累积：当前帧权重 0.1、邻域裁剪 σ 1.0、重置（= 相机切换后前 4 帧） |
| 31–33 | `uFog`、`uFog2`、`uFog3` | 浓度、高度衰减、基准高度、各向异性 g；近 0.1、远（Max Distance）、环境光、噪声；雾颜色、开关 |
| 34–35 | `uHF`、`uHF2` | 高度场 AO：顶视图中心 x / z、宽度、相机高度；开关、强度、半径、方向数（High 8 / Low 4） |
| 36 | `uRT` | 探针 GI 开、光追反射开（都已乘上总开关和 Available）、反射最大粗糙度、GI 强度 |
| 37–38 | `uRT2`、`uRT3` | 探针网格最小角 xyz、每探针光线数（64 / 32）；探针间距 xyz、亮度上限 16 |
| 39 | `uRT4` | 光追反射网格宽、高（分辨率 ÷ 4 / ÷ 6）、反射混合强度 |

40 个槽位已经用满；再加功能要把 `NSLOT`、`common.glsl` 的数组长度和测试里的 4 × 40 一起改。

- `UNI.CAMERA`：读相机 `worldTransform`，列向量归一化。上一帧相机和帧计数存在模块级字典 `_STATE` 里（不随文件保存）。帧计数 < 4 时置历史重置标志（`uFrame.z`）。这个 CHOP 必须每帧计算（`BUILD.UNICOOK`），否则帧计数不走、重置标志一直是 1。
- `UNI.RECOOK`：同一帧里被计算第二次时（比如帧开始的 `run()` 回调里读了它或下游 TOP 的像素），不推进历史：继续用上一帧的相机、帧号和抖动。否则第二次计算时"上一帧相机" = 当前相机，TAA 和运动模糊在这一帧看不到运动（0.2.0 开发中踩过：截图工具在回调里存图，存出来的运动模糊图没有拖影）。
- `UNI.JITTER`：Halton(2,3) 8 个样本，范围 ±0.5 像素。写进 `cam_jit` 的 Window X / Y（= 用户相机的值 − 抖动/2；实测 Window X 每 +1，NDC 平移 −2），下一帧 G-Buffer 用。只在值变化时写。
- `UNI.SS` / `UNI.FOG` / `UNI.HFAO`：Indirect 页、Fog 页 → 槽位 27–35。`UNI.RT` / `UNI.RTSTATIC` / `UNI.RTXFORM` / `UNI.RTCHECK`：见 §9d。
- `UNI.POST`：Post 页 → 槽位 21–26。焦距为 0 时由相机水平视角和传感器宽度反算；打开自动曝光的那一帧置重置标志，曝光直接跳到目标值（不从 1 倍慢慢适应）。
- `UNI.FOV`：兼容 Camera COMP 的三种视角设置方式（水平 FOV、垂直 FOV、焦距）。
- `UNI.SUN`：主光强度 = Dimmer × π × Intensity Multiplier（原生 PBR MAT 里 Dimmer 1 相当于辐照度 π，这样换成 BTDR 后亮度一致）。
  阴影相机的基向量从内部的 `suncam` 读回来。
- `UNI.PARAMS`：把参数页的值写进槽位。脚本里读了参数，所以改参数会触发重算。
- `UNI.PARCACHE`（0.5.1）：每帧约 120 次读参数。`C.par.Bloom` 这种按属性名查找在 TD 里约 0.65 µs，`eval()` 本身约 0.12 µs；所以按 OP 的 `id` 缓存 Par 对象（`_pars(o)`，组件重建 / 重新载入后 id 变，自动重建缓存），每帧只 `eval()`。表达式、导出照常生效。
- `UNI.RTSTATICKEY`（0.5.1）：`rt_static` 的变化判断直接比较 7 个槽位的元组（同样的输入算出的浮点数逐位相同）；0.4.0 每帧把 160 个数 `round` 一遍（约 0.07 ms）。
- 0.5.1 实测（示例场景 demo，5080 Laptop）：`uniforms` 0.54 → 0.45 ms。剩下的大头是读灯光和阴影相机的变换：灯开着原生阴影时，这一步会把灯自己的计算（约 0.4 ms）算进来（`EXT.TIPS`）。
- 这个 CHOP 靠参数 `Frame`（表达式 `absTime.frame`，`BUILD.UNICOOK`）每帧计算一次；0.3.1 以前只在回调里读 `absTime.frame`，相机静止时不计算（§11 第 23 条）。回调本身约 0.1 ms（`UNI.CAMBASIS`：纯 Python 读 `Matrix.vals`，不用 numpy）；profile 里记到它头上的时间还包括它读别的节点时触发的计算：`suncam`，以及开着原生阴影的 Light COMP（§11 第 18 条，示例场景里约 0.4 ms）。

## 5. 扩展类 `BTDRExt.py`

| 锚点 | 内容 |
|---|---|
| `EXT.REFRESH` | `Refresh()`：解析三个参数 → 建镜像 → 自动阴影范围 → 摆阴影相机 → 写状态和警告 |
| `EXT.RESOLVE` | 路径模式的解析规则：相对于 `renderBTDR` 的父网络，空格分隔，支持通配符和绝对路径 |
| `EXT.MIRROR` | 场景镜像（见下） |
| `EXT.MATERIAL` | 镜像材质对源材质的表达式绑定 |
| `EXT.INSTANCING` | Instance 页所有参数用表达式跟随源几何体 |
| `EXT.SHADOWFIT` | 按包围盒算阴影中心和范围；扁平物体（最短边 < 最长边的 2%）不参与；范围 = 包围盒对角线 × 1.6 |
| `EXT.SUNCAM` | `SunLocal()`：阴影相机在主光局部空间里的位置 |
| `EXT.STATUS` | 警告的上报方式：存进 storage 的 `status`、写到 Status 参数和 `status` DAT；由 `uniforms` 在下次计算时调用 `addWarning`（`UNI.WARN`） |
| `EXT.QUALITY` | 档位表 `QUALITY`；`ApplyQuality()` 把档位值写进对应参数 |
| `EXT.JITCAM` | `_setup_jitcam(cam)`：`cam_jit` 的父物体设成用户相机（自身变换为 0），投影类型、视角、近远裁剪等镜头参数用表达式跟随；`gbuffer` 的相机设成 `cam_jit` |
| `EXT.SHADOWWATCH` / `EXT.CASTERS` | 阴影缓存要监视的对象；投射阴影的物体列表（见下） |
| `EXT.RTPROXY` / `EXT.RTMAT` / `EXT.RTGRID` | M4：光追代理链、每物体材质表、探针网格范围（§9d） |
| `EXT.TIPS` | 0.5.1：不算问题、但白白耗时的场景设置，写进 Status（不加警告标记）和 `status` DAT（`tip:` 开头），`status` 存储里是 `tips`。目前一条：主光开着原生阴影（Shadow Type ≠ Off） |

### 场景镜像（`EXT.MIRROR`）

原因：延迟渲染要求所有几何体用同一套 G-Buffer 着色器，但用户的几何体挂的是原生材质。
M0 验证过：COMP 不能当材质用，MAT 不能加自定义参数页，所以不做专用材质，改为在内部复制一份场景。

对 `Geometry` 匹配到的每个 Geometry COMP，在 `scene/` 里建一个 `gN`：
- 源里每个开了 Render 标志的 SOP → 一个 Select SOP；POP → Select POP。
- `Parent Transform Source = specify`，`Parent Object = 源`：镜像自己不带变换，完全继承源的世界变换。
- `Render` 参数用表达式跟随源。
- 材质 = `scene/mK`，每个不同的源材质对应一个。

`EXT.MATERIAL`：`mK` 是 GLSL MAT（`gbuffer.vert / .frag`），它的 uniform 和贴图全部是指向源材质参数的表达式，
例如 `op('/project1/geo/pbr1').par.roughness`、`op(...).par.basecolormap.eval() or parent.BTDR.op('white')`。
所以改源材质参数实时生效；换材质节点、改名则要 Refresh（表达式里是绝对路径）。

### 阴影相机（`EXT.SUNCAM`）

`suncam` 是正交相机，`Parent Object = 主光`，自身旋转为 0，所以朝向永远和灯一致（灯和相机都朝 −Z）。
平移是 `SunLocal()` 算出的常量：把 Shadow Center 变换到灯的局部空间，再沿 +Z 退后 `max(10, 范围×1.5)`。
0.1.2 起不再用表达式（Python 表达式每帧都会重新求值，约 0.1 ms），由 `uniforms` 每帧比较、只在结果变化时写入（`UNI.SHADOWCACHE`）。
这样灯怎么转，阴影视锥都以 Shadow Center 为中心（已验证：灯转 70° 后中心偏移为 0）。
`SunLocal()` 用纯 Python 算（不用 numpy），并按输入（中心、范围、灯的变换）缓存。
没有灯时不设父物体，用内置方向 (0.55, 0.75, 0.50)。

### 阴影图缓存（`UNI.SHADOWCACHE`、`EXT.SHADOWWATCH`、`BUILD.SHADOWUPDATE`）

TD 的 Render TOP 只要被下游拉取就每帧重画（实测静态场景、静态相机也是）。所以 `lighting` 不直接读 `shadow`，而是读它后面的 Cache TOP `shadow_cache`（缓存 1 帧）：
Cache TOP 不激活（Active 关）时不拉取输入，`shadow` 就不再重画，输出保持最后一张阴影图。

- `Refresh()` 把要监视的对象存进 storage 的 `shadow_watch`：主光、每个源 Geometry COMP（看世界变换），以及它们开了 Render 标志的 SOP / POP 和实例化源（看 `totalCooks`）。
- `uniforms` 每帧算一个签名：`SunLocal()`、Shadows / Shadow Resolution / Shadow Range，加上面这些对象的世界变换和 `totalCooks`。
  签名这一帧或上一帧变过（多留一帧，避免停下来那一帧的阴影慢一拍）、或 Light 页 Shadow Update = Every Frame 时，把 `shadow_cache.active` 打开，否则关闭。
- 相机动不影响阴影图，所以环绕相机的场景阴影图一直不用重画。
- **计算顺序（实测）**：一帧里 `lighting` 先计算它的输入（`shadow_src` → `shadow_cache` → `shadow`），最后才计算 `uniforms`。所以 `uniforms` 读到的 `suncam` 状态正是这一帧画阴影图用的状态；它先把这个基向量存成 `mapv`，再把 `suncam` 挪到下一帧要用的位置。没重画的帧继续用 `mapv`，查表的基向量永远和阴影图一致（0.1.2 早期版本先挪后读，光源动的时候会错一帧）。
- `UNI.SHADOWMOTION`（光源或物体在动时）：
  - **Half Resolution While Moving**（默认开）：阴影图分辨率减半；停下后用全分辨率再画一次。
  - **Update Every N Frames While Moving**（默认 1）：大于 1 时每 N 帧才重画一次，中间帧用缓存。
  - 每帧都重画时（N = 1 或 Every Frame），`lighting` 经 Switch TOP `shadow_src` 直接读 `shadow`，跳过 Cache TOP：Cache TOP 每帧复制阴影图实测要 0.3–1.2 ms GPU。
- `UNI.HFCACHE`：高度场 AO 的 `hf_cache` 跟着同一个签名走（签名里加了 Height-Field AO 开关，打开时会画一次）：阴影图要重画的帧它也激活（包括直接读 `shadow` 的帧），其余时间保持最后一张。
- `EXT.CASTERS`：地面只接收阴影、不投射：Y 方向扁平（高度 < 宽度的 2%）且不高于其他所有物体最低点的 Geometry COMP 不进阴影渲染（`shadow` 的 Geometry 参数是投影物体列表）。
- 没覆盖到的情况：几何体在 Geometry COMP 里**没有**开 Render 标志的上游节点变了但渲染节点没重新计算（实际上不会发生）；材质的顶点变形（自定义 GLSL MAT 不支持，原生材质没有）。保险起见可以把 Shadow Update 设成 Every Frame。

## 6. G-Buffer（`gbuffer.vert / .frag`）

| 缓冲 | rgb | a |
|---|---|---|
| RT0 `gbuf0` | 基础色（线性） | 金属度 |
| RT1 `gbuf1` | 世界法线 | 粗糙度 |
| RT2 `gbuf2` | 相对相机的坐标（世界坐标 − 相机位置） | 材质 AO |
| RT3 `gbuf3` | 自发光（线性） | — |

- 顶点属性一律用 `TDPos()`、`TDNormal()`、`TDTexCoord(0)`：SOP 和 POP 通用。**直接写 `P`、`N`、`uv[0]` 时 POP 几何体画不出来**（踩过）。
- 实例化由 `TDDeform()` 自动处理，着色器里不用管。
- `GBUF.SHARED`：材质着色器（`gbuffer.*`、`shadow.*`）不拼 `common.glsl`，也不读任何每帧变化的 uniform，所以镜像材质不会每帧重新计算（每帧省约 0.18 ms CPU）。
  TAA 抖动放在 `cam_jit` 的投影里（`EXT.JITCAM`），着色器完全不知道抖动。0.1.2 的 `jitter` CHOP 和 `uJ[1]` 已删除。
  相机位置取 `uTDMats[…].camInverse[3]`，sRGB 开关放在每个材质的 `uChan.w` 里。
- `GBUF.RELPOS`：RT2 写 `worldPos − camPos`。`lighting`、`depth`、`debug` 读的时候加回 `uCamPos`（视线方向直接用 `-rp`）。
- `GBUF.NCONV`：`uPBR.w` 为负表示 DirectX（Y−）法线贴图，翻转切线空间的 y。符号来自 Render 页的 Normal Map Convention（`EXT.NCONV`）。
- `EXT.ANISO`：所有贴图采样器开 4× 各向异性过滤，斜看的表面贴图不会糊。
- `GBUF.MATERIAL`：`uBase`、`uPBR`（金属度、粗糙度、AO 强度、法线贴图强度）、`uEmit`、`uChan`（三张贴图的 Channel Source 菜单序号）。
- `GBUF.NORMALMAP`：切线空间由屏幕空间导数现算，不需要切线属性。
- `GBUF.NORMAL`：几何体没有法线属性时，用世界坐标的导数算平面法线。
- sRGB：`uChan.w` 为 1 时（跟随 Render 页的 sRGB 开关），基础色和自发光的颜色参数、贴图都做 2.2 次幂转线性。背景颜色用的是 `uView.y`。
- 背景判定：法线长度平方 < 0.25。

## 7. 环境（`env_studio.frag`、`env_prefilter.frag`、`env_lookup.glsl`）

- `ENV.STUDIO`：程序化摄影棚画成 1024×512 的全景图，只算一次。
  柔光箱比旧管线小 25%：旧管线的漫反射环境光是近似公式，偏暗；现在是真实卷积，为了保持同样的明暗关系缩小了灯箱。
- `ENV.PREFILTER`：`env_atlas` 是 256×128×6 的 3D 纹理。第 0–4 层是粗糙度 0.2、0.4、0.6、0.8、1.0 的 GGX 预滤波（96 个采样，按 pdf 选源图 mip）；
  第 5 层是余弦卷积的辐照度（已除以 π）。只在环境源变化时重算。
- `ENV.LOOKUP`：`envRadiance(方向, 粗糙度)`：粗糙度 < 0.2 时在清晰全景和第 0 层之间插值，否则在图集层间三线性插值；
  `envIrradiance(法线)` 取第 5 层。这份代码通过 `//#include env_lookup` 引入，**全套只有这一份**（旧管线有 4 份拷贝）。
- 光照节点的输入延伸方式设成 Repeat，全景图左右接缝才连续。

## 8. 光照（`lighting_core.glsl`，`lighting.frag` 和 `composite.frag` 共用）

- `FILE.LIGHTCORE`：`lightingTerms(uv, …)` 算出四项（`LIGHT.SPLIT`）。采样器用宏指定（`LC_BASE / LC_NRM / LC_POS / LC_EMIT / LC_SHADOW`，环境用 `ENV_SHARP / ENV_ATLAS`），两个宿主的输入编号不同。阴影纹素大小取自 `textureSize(LC_SHADOW)`（以前是 `uTD2DInfos[3]`，绑死了输入编号）。

- BRDF 和旧管线相同：GGX + Smith 联合可见性近似 + Schlick 菲涅尔。
- `LIGHT.SHADOW`：阴影图存线性距离。12 点遮挡体搜索 → 半影估计 → 24 点 PCF（Vogel 圆盘）。
  和旧管线的区别：所有半径用**世界单位**（搜索半径 0.024 × Softness，光源角直径系数 0.0376），所以结果不随阴影图分辨率和范围变化；偏移量加了 1.5 个阴影纹素。
- `LIGHT.IBL`：环境漫反射 + 环境镜面（UE 的 EnvBRDFApprox），镜面遮蔽和地平线衰减同旧管线。
- `LIGHT.SPLIT`：4 项——直接光 + 自发光（+ 背景）、环境漫反射、环境镜面、环境 BRDF | 权重。M3 / M4 在 `composite` 里替换环境项。0.5.1 起这四项在 `composite` 里现算（寄存器里，不再写成四张 16 位缓冲再读回来）；`lighting.frag` 把同一份代码写成四个缓冲，只在 Debug View 的直接光 / 环境漫反射 / 环境镜面 / 反弹光 / 反射几项时计算。
- `LIGHT.BACKGROUND`：纯色或环境（按 Background Blur 取模糊层）。直接光缓冲的 alpha：1 = 物体，0 = 背景。
- `LIGHT.FADE`：按到相机的距离淡入背景（旧管线是按到世界原点的水平距离，写死 4–9）。

## 9. 合成、调色、调试

- `composite.frag`：直接光 + 环境漫反射 × AO + 反弹光 + 环境镜面 / SSR（M3，见 §9c）。旧管线里探针和光追反射的合成在 M4 移植到这里。
- `COMP.INLINE`（0.5.1）：光照项在这里调用 `lightingTerms` 现算。0.5.0 及以前 `lighting` 先写四张 rgba16float 缓冲（1080p 每帧约 130 MB 读写）、再经 3 个 Render Select 给 `composite` 读：少了 4 个 TOP 的计算和这部分带宽。图像差别只来自少了一次 16 位量化（A/B：最终画面平均 |差| 0.0004，差异集中在物体轮廓的单像素上，TAA 邻域裁剪放大了量化差，肉眼看不出）。输入延伸方式改成 Repeat（环境全景要左右绕回），可能比输出小的输入（Low 档半分辨率的 SSGI / SSR、光追反射、高度场）用 `texHold()` 把坐标夹到边缘纹素中心，等于原来的 Hold。
- `GRADE.BLOOM`：Bloom 在 HDR 里、曝光之前加（和 UE 一样）：`bloom_src × 强度`（mip 链已经合成好，见 §9b）。
- `COMP.PROBES` / `COMP.RTSPEC`（M4）：探针替换环境漫反射；光追反射比值乘环境镜面，见 §9d。
- `GRADE.EXPOSURE`：手动曝光（EV）× 自动曝光倍数（输入 2 `ae_exposure` 的 g；关闭时为 1）。
- `GRADE.ACES`（`grade.frag`）：曝光 → ACES 拟合 → 暗角 → sRGB → 颗粒。
- `DEBUG.VIEWS`（`debug.frag`）：序号 = Debug View 菜单里的位置；0（最终画面）由 `view` Switch TOP 处理，这时 `debug` 不计算。
- `depth.frag`：第 3 个输出。

## 9b. M2：时间性抗锯齿和镜头效果（0.2.0）

算法都从旧管线 `archive/ue5r/shaders/` 移植，改动是接到 BTDR 的相对相机坐标和共享 uniform 数组上。
运行顺序：`composite` → `taa` → 景深 → 运动模糊 → Bloom / 自动曝光测光 → `grade`。景深、运动模糊关闭时 Switch TOP 直接旁路，节点不计算。

**TAA（`taa.frag`）**
- 抖动方式（`EXT.JITCAM`、`UNI.JITTER`）：G-Buffer 通过内部相机 `cam_jit` 渲染，抖动是它的投影偏移（Window X / Y）。
  旧管线是在材质顶点着色器里加抖动，那样每个材质每帧都要重新计算；用投影偏移材质完全不用动。
- `TAA.REPROJECT`：用 G-Buffer 位置分别投影到当前和上一帧的**不含抖动**的相机，差值就是屏幕运动，不需要运动矢量缓冲。只覆盖相机运动；物体自己动时靠下面的邻域裁剪兜底（轻微拖影）。
- `TAA.HISTORY`：历史帧用 5 次采样的 Catmull-Rom 读取，重投影时不发糊。
- `TAA.CLIP`：3×3 邻域在 YCoCg 空间求均值和方差，历史颜色裁剪到 均值 ± γσ（γ = 1.25）。历史在屏幕外、或 `uFrame.z`（相机切换后前 4 帧）时直接用当前帧。
- 混合权重 = Render 页 TAA Current Frame Weight（默认 0.1）。
- `TAA.DEPTH`：输出 alpha 写**稳定的视深**（沿相机朝向的距离，不随抖动跳动），景深和运动模糊都读它，第 2 个输出也带着它。

**景深（`dof.frag`）**
- `DOF.COC`：薄透镜模型的弥散圆半径（像素）= f² / (N × (s − f)) × |d − s| / d，换算到输出像素用传感器宽度；上限 Max Blur Radius。焦距 0 时由相机视角反算（`UNI.POST`）。
- 采样：单遍"以收代散"（scatter-as-gather）的黄金角螺旋（Dennis Gustafsson 的做法），半径每步加 步长 / 半径，步长随 Quality（High 1.25、Low 2.0）。
  比当前像素更远的采样点，其弥散圆限制在当前像素的 2 倍以内：背景不会渗到清晰的前景边缘上。

**运动模糊（`mblur.frag`）**
- `MB.VELOCITY`：和 TAA 一样用前后两帧不含抖动的相机投影出每个像素的屏幕速度，乘快门；沿速度方向 12 / 6 个采样，每像素随机起点（加帧号）避免条纹。
- 只有相机运动；物体自身的运动需要逐物体的运动矢量（需要材质输出上一帧变换，列在 §12）。
- 相机绕着某点转时，这个点附近的像素速度接近 0、不会糊，越远越糊——是正确的物理结果，验证时别误判成"没生效"。

**Bloom（`bloom_pre.frag`、`bloom_down.frag`、`bloom_up.frag`）**
- `bloom_pre`：按**曝光之后**的亮度做软膝阈值（输入 1 是 `ae_exposure`），同时降到 ½ 分辨率。阈值 1 = 屏幕上刚好变白的亮度，自动曝光开关不会让泛光忽多忽少。
- `BLOOM.CHAIN`（0.3.5，`BUILD.BLOOM`）：mip 链，和 UE / COD: Advanced Warfare 的做法一样。
  - 下采样 `bloom_d1`–`bloom_d6`（¼ … 1/128），每级 13 点（Jimenez 2014），采样偏移按**输入**纹理的像素算。第一级（`bloom_karis_frag`，`#define BLOOM_KARIS`）用 Karis 加权平均，单个极亮像素不闪。
  - 上采样 `bloom_u5`–`bloom_u0`：把粗一级做 3×3 帐篷滤波，和本级按 Bloom Radius（`uBloom.w`，默认 0.65）混合：`mix(本级, 帐篷(粗一级), 半径)`。是加权平均，所以半径不改变总亮度。结果 ½ 分辨率，`grade` 只读这一张。
  - 级数是构建常量（`BLOOM_LEVELS`，默认 6）。`BUILD.BLOOMLOW`（0.5.0）：Quality = Low 时 `bloom_u3` 的粗一级改接 `bloom_d4`（Switch `bloom_lvl`），最粗的两级不再被拉取、不计算（省 4 个 TOP 的 CPU），光晕最大范围约为 High 的 1/4。
  - Bloom Intensity = 0 时 `bloom_src`（Switch）切到常量黑，整条链不计算。
- 0.3.4 及以前是两级可分离高斯（½ 和 ⅛），⅛ 那级的水平模糊从 ½ 分辨率的输入取样，偏移按输入像素算，等于没有水平模糊：小亮点的光晕是竖长、两侧硬边的椭圆（"方块状光晕"），由 `BLOOM.CHAIN` 修复。

**自动曝光（`lum.frag`、`exposure.frag`）**
- `FILE.AE.METER`：在 256×144 上算中心加权的 log2 亮度（r = log2 L × 权重，g = 权重），Analyze TOP 求平均，平均 log 亮度 = r / g。
- `AE.ADAPT`：1×1 的 `ae_exposure` 读自己的上一帧（Feedback `ae_hist`），在 log2 空间按帧时长指数逼近目标曝光 = 目标灰 / clamp(测光亮度, 2^Min EV, 2^Max EV)；画面变亮、变暗用不同速度。打开自动曝光的那一帧（重置标志）直接跳到目标值。关闭时输出 1 倍。输出 r = log2 曝光、g = 曝光倍数、b = 测光亮度。
- 示例场景测光亮度约 0.16，和目标灰 0.18 接近，所以开自动曝光后画面只亮约 15%；对暗场景 / 亮场景的效果更明显。

## 9c. M3：屏幕空间间接光和体积雾（0.3.0）

全部从旧管线移植。共用的屏幕空间工具函数在 `ss_common.glsl`（`FILE.SSCOMMON`：投影、取相对相机位置、交错梯度噪声）。
"上一帧画面"统一从 `taa_hist` 读（上一帧 TAA 的结果，还没有 Bloom 和调色），用不含抖动的上一帧相机重投影。
因此 `taa_hist` 的输入不能再接 `composite`（会形成 composite → ssgi → taa_hist → composite 的依赖环），改接尺寸、格式相同的 `gbuf0`。

**AO + 反弹光（`ssgi.frag`）**
- `SSGI.HORIZON`：GTAO 式的切片扫描。每个方向两侧沿屏幕走若干步，记录"地平线"抬升；每次被某个采样点抬高时，新挡住的那部分半球（余弦加权，用仰角正弦的平方度量）既是遮蔽，也是这个采样点的反弹光（读它上一帧的亮度）。一次扫描同时得到 AO（a）和间接漫反射（rgb）。
- `SSGI.BIAS`：16 位相对相机坐标有约 0.05% 距离的量化误差，平面在掠射角下会自遮挡出等高线状条纹。做法：忽略距离小于 0.2% 视深的采样，切平面抬高 0.08（正弦）。
- 半径是世界单位，换算成像素后上限为画面宽度的 1/4。

**SSR（`ssr.frag`）**
- 每像素一条按 GGX 重要性采样的反射光线（截掉最长的 15% 尾部降噪），世界空间步进（`SSR.MARCH`：二次分布，近处密），读命中点上一帧的亮度。
- `SSR.REFINE`（0.3.5）：光线从"在深度缓冲前面"变成"在后面"的那一步，先二分细化 7 次回到交界处，再在细化后的点上做厚度测试（物体厚度 + 5% 距离）；不过就继续往前走（光线从物体后面穿过）。0.3.4 及以前在粗步的采样点上做厚度测试，命中与否取决于步子正好落在哪里：厚度大时反射边缘是阶梯状，厚度小时漏掉命中、出现横向条纹。
- `SSR.SELFHIT`：命中点离起点很近（< 0.01 + 1% 视距）**并且**命中处的法线和起点的几何法线（不含法线贴图，用位置的屏幕导数算）基本同向时，算没命中——那是法线贴图、刻字等细节重新钻进粗糙的 G-Buffer 表面，不是反射到的物体。0.3.0 只看距离，把物体贴地处的近距离命中也扔掉了，倒影和物体之间留出一条露出环境反射的缝，0.3.1 修复。
- `SSR.CONFIDENCE`：屏幕边缘、接近粗糙度上限、接近最远距离、朝相机方向（`dot(R, -V)` 0.3–0.7）时淡出，淡出部分用环境反射。
- 示例场景里正对镜头的铜牌：反射光线朝左下打到深色地面，SSR 结果比环境反射暗——这是对的（环境反射不知道地面挡住了天空）。

**时间累积（`ss_accum.frag`）**
- 两条链共用：按表面运动重投影历史，3×3 邻域均值 ± σ 裁剪；`ACCUM.MOTION`：画面运动越快，越不信历史（权重从 0.1 升到 0.5、裁剪收紧），因为反射和反弹光的运动和表面不同，历史会拖影。
- NaN 保护：历史是 NaN / Inf 时直接用当前帧（TAA 同样处理，`TAA.NAN`），一帧坏数据不会永久污染反馈链。
- `SS.HISTRESET`（0.5.0，`ssgi.frag`、`ssr.frag`）：历史重置帧（`uFrame.z`）不读 `taa_hist`——反弹光取 0，SSR 直接输出 0。读到的 `taa_hist` 本身也做 NaN / Inf 保护。原因见 §11 第 32 条。

**合成（`composite.frag`）**
- `COMP.AO`：AO 只压暗环境漫反射；反弹光 = 漫反射色 × SSGI × 强度，加在上面。环境镜面按 AO 的一半压暗。
- `COMP.SPEC`：SSR 置信度高的地方用 SSR × 环境 BRDF 替换环境镜面。
- `COMP.HFAO`（0.3.3）/ `COMP.HFRECEIVER`（0.3.4）：高度场 AO，0.3.4 起只作用在接收者上：法线 y > 0.6、且该位置顶视图高度比自己高出 3 cm + 0.3% 视距以上（或该位置没有物体）的表面——地面、车底、车内座椅这类被罩住的面；物体的侧面、顶面、朝下的面不算。0.3.3 对所有表面生效，车身侧面被自己的车肩当成遮挡压暗，看起来发脏。顶视图存"相机以下的深度"，高度 = 相机高度 − 值，0 = 没有物体。每个像素沿 8 / 4 个水平方向（每像素随机旋转，TAA 平均）各走 4 步（平方分布，最远 = Radius），记录遮挡物相对表面切平面的最大仰角，该方向可见天空 = 1 − sin²(仰角)（余弦加权）。方向按法线加权（`clamp(dot(d, N) + N.y)`）：朝上的面看全部方向，竖直的面只看朝外的方向，朝下的面不算；起点沿法线抬 2 cm + 0.2% 视距（16 位位置精度）。与屏幕空间 AO 取较小值压暗环境漫反射；环境镜面再整体乘高度场项（车底地面里映出的天空要被挡掉）。坐标：`topcam` 绕 X 转 −90°，屏幕右 = +X、屏幕上 = −Z，所以 `uv = (x − cx, cz − z) / 宽度 + 0.5`（已用平移中心的方法实测确认）。局限：物体从顶面到地面算实心；只看从上方来的遮挡。开销（1080p High，CarConcept 场景）：`composite` GPU 0.07 → 0.34 ms；`hf_render` 重画一次 0.035 ms。
- Debug View 11–13（AO、反弹光、反射）在 `debug.frag` 里算（`DEBUG.SS`），**不能**放在 composite：composite 之后是 TAA，它的历史就是屏幕空间 pass 读的"上一帧"，调试画面放进去会反馈回来（试过：反弹光和反射的调试画面变成全黑，因为上一帧是黑的）。

**体积雾（`fog_scatter.comp`、`fog_accum.comp`、`fog_integrate.comp`、`fog_apply.frag`）**
- 格子（froxel）跟相机视锥对齐：x、y 是屏幕，z 按指数分布切片（`FOG.SLICES`，近 0.1 到 Max Distance）。High 160×90×64，Low 128×72×48。
- `FOG.DENSITY`：指数高度雾 × 可选的动态噪声。`FOG.SHADOW`：每个格子用 2×2 PCF 查和表面相同的阴影图——被挡住的格子只有环境光，这就是光束。太阳项乘 Henyey-Greenstein 相位函数（各向异性 g）。环境项 = (上方 + 下方辐照度/π) / 2 × Ambient Light。
- `FOG.JITTER`：每帧在格子内随机取一个点（x、y、z 三个方向都抖）。
- `FOG.ACCUM` / `FOG.REPROJECT`（0.3.2）：在 3D 格子里做时间累积——每个格子中心按上一帧相机算出它在上一帧体积里的位置，三线性读历史，按 0.1 混入当前帧（和 UE5 一样）；历史重置或位置落在上一帧体积外时只用当前帧；结果有 NaN 时丢弃历史。**为什么不能只靠 TAA**：一个格子在屏幕上约 12×12 像素，同一格子的噪声在 TAA 的 3×3 邻域里是常数，方差裁剪会把历史判成无效，噪声永远平均不掉，光束被淹没（0.3.1 及以前的问题）。代价：雾对灯光、浓度变化的反应约慢 10 帧。
- `FOG.INTEGRATE`：每列一个线程从前往后积分（Hillaire 2015 的能量守恒步进），每个切片存"相机到这个切片中点"的累计散射光和透射率。
- `fog_apply`：按像素深度查积分结果，`颜色 × 透射率 + 散射光`，切片位置加半格随机抖动消除分层。`FOG.EDGE`：查找位置限制在第一个和最后一个切片中心之间（3D 输入在深度方向是重复寻址的，s = 1 会混进第一片，曾在 Max Distance 处出现一条硬边）。
- `fog_accum` GPU 约 0.025 ms。
- 为什么用计算着色器：像素着色器版本每个切片一次绘制，64 片 × 2 个 TOP 实测 CPU 多 1.2 ms、积分 pass 还是 N²/2 次读取（GPU 0.7 ms）；计算着色器版本整套雾 GPU 约 0.1 ms、CPU 约 0.13 ms。

## 9d. M4：硬件光追（简化版 Lumen，0.4.0）

从旧管线阶段 5 移植，主要改动是"光追场景"不再离线生成：节点内部从镜像的几何体实时建代理，跟着物体移动。

**光追代理（`EXT.RTPROXY`，`BTDRExt._rt_build`）**
- 每次 Refresh 重建 `rtscene/`：每个源 Geometry COMP 的每个开了 Render 标志的 SOP 一条链：Select SOP → Convert SOP（转多边形；Grid SOP 默认是 mesh，SOP to POP 后没有图元）→ PolyReduce SOP（Keep % = Proxy Detail，表达式绑定，改了立即生效；默认预三角化）→ SOP to POP。POP 源直接 Select POP（不减面）。
- → Transform POP，矩阵来自表 `rtscene/xf<i>`（Xform Matrix/CHOP/DAT 参数只接受 DAT / CHOP，不接受 COMP；4×4 行主序 = `worldTransform[r, c]`，已逐点验证）→ Attribute POP 写点属性 `ObjId` = 几何体序号 → `merge` → `tri`（Convert POP，Quads to Triangles：加速结构只接受三角形）→ `out`。
- 链上每个节点都缓存：PolyReduce 只在源变化时重算（4.9 万面约 0.14 s）；物体移动只让 Transform POP 重算。
- `UNI.RTXFORM`：`uniforms` 在阴影签名变化时比较每个源的世界矩阵，变了才重写对应的 `xf<i>` 表。
- 实例化的几何体暂不进代理（警告）。
- 示例场景 11.5 万面 → 1.7 万面；CarConcept 21 万面 → 3.2 万面。

**材质（`EXT.RTMAT`）**：`rt_mat` 表每个物体两行：反照率 rgb | 金属度、自发光 rgb | 0（线性）。值 = 材质颜色参数 × 贴图平均色（`rtscene/avg_sel` → `avg_res` 16×16 mipmap 降采样后 numpy 求平均；sRGB 开时先 2.2 次幂）。只在 Refresh 时算。GLSL POP 的 Arrays 页把 `rt_mat_chop` 当纹理缓冲 `rtMat` 读：`texelFetch(rtMat, 2 * ObjId)`。

**光线查询（`rt_common.glsl`）**
- `RT.TRACE`：最近交点；面法线由三角形三个角的位置叉乘得到（代理不需要法线属性），`RT.FACESIGN` = +1（在测试场景地面上实测：从上往下的光线打到地面，叉乘的 y 为正）。`backface` = 法线与光线同向。
- `RT.SHADE`：命中点只做漫反射（Lumen surface cache 的质量）：反照率 × (`RT_AMBIENT` + 太阳 × 阴影光线) + 自发光。`RT_AMBIENT`：探针 pass 里是环境辐照度 × 0.5；反射 pass 里探针 GI 开时用探针（知道遮挡：车底盘是暗的），否则环境辐照度 × 0.5。

**探针 GI（`rt_probes.comp`，`BUILD.RTPROBES`、`EXT.RTGRID`）**
- `rt_probe_grid`：Grid POP 点阵 16×8×16（Low 12×6×12），范围 = 实心物体包围盒 + 15% 边距（至少 0.2），底面在物体最低点上方 3 cm、顶面高出 25%。3D 纹理的 texel (i,j,k) = 最小角 + (i,j,k) × 间距（已实测：POP to TOP 的 3D 布局 x = cols、y = rows、z = slices）。
- 每探针 64 / 32 条球面斐波那契光线（每探针随机旋转），没打中取 `envRadiance(d, 0.5)`，打中取 `shadeHit`，打到背面计数；输出 SH0 = 平均辐射度 | 有效性，SH1..3 = r/g/b 一阶矩 × 3；`RT.PROBEVALID`：背面比例 > 20% 判为在物体内部。
- `UNI.RTSTATIC`：探针 pass 不读每帧变化的 `uniforms`，而读 `rt_static`（只保留槽位 10–12、15、36–38，并清掉与探针无关的项），只在这些值变化时重写表 → 静态场景里探针一次都不重算（测试 `TEST.RTSTATIC`）。
- `GI.PROBE_SAMPLE`（`probe_lookup.glsl`，composite、debug、rt_refl 共用）：8 个相邻探针三线性 × 有效性 × 方向权重（偏向表面前方的探针）。
- `COMP.PROBES`：探针开时环境漫反射 = 漫反射色 × 探针辐照度 × 材质 AO × GI 强度；SSGI 反弹光减半（探针已含大尺度反弹）。屏幕空间 AO、Height-Field AO 照常相乘。

**光追反射（`rt_refl.comp`，`BUILD.RTREFL`）**
- 每帧一个 GLSL POP，点阵 = 输出分辨率 ÷ 4（Low ÷ 6），每点一条 GGX 重要性采样的反射光线，从 G-Buffer 读法线 / 粗糙度 / 相对位置。
- `RT.OFFSET`：起点沿法线抬 1 cm + 0.3% 视距，最近交点距离 2 cm + 0.6% 视距（代理是减面的，和真实表面差几厘米；太小时车身出现自相交的黑点）。
- `RT.RATIO`：输出 追踪结果 ÷ 无遮挡环境（上限 4，防亮点）；没打中 = 1。`RT.BACKFACE`：起点附近打到背面（在代理内部出发）= 无效；远处的背面当作另一面绕序的真实表面双面着色（单面或绕序不一致的网格，例如车底）。
- `ACCUM.RT`（`rt_accum_frag` = `#define RT_ACC` + `ss_accum.frag`）：粗糙表面先做 3×3 均值（全分辨率 12×12），当前帧权重 0.06、裁剪 1.5σ。
- `COMP.RTSPEC`：环境镜面 = mix(环境镜面, 环境镜面 × 比值, 有效 × 开关 × 强度)；光追有效处不再乘 Height-Field AO（遮挡已包含在比值里）；SSR 照旧叠在最上面。

**加速结构（`BUILD.RTAS`）**：GLSL POP 每次计算都重建加速结构。Fast Trace 构建 3.2 万面约 0.65 ms，Fast Build 约 0.03 ms（含 13 万条光线，5080 Laptop，`gpuCookTime` 实测）：每帧计算的反射用 Fast Build，很少重算的探针用 Fast Trace。

**不支持光追时（`UNI.RTCHECK`）**：Refresh 后第 30 帧强制计算两个 GLSL POP 读 `errors()`（刚建出来时可能残留编译错误，所以先强制计算）；有错就把只读参数 Rtavailable 关掉，Switch 切到 `rt_off` / `rt_probe_off`（2×2×2 全零 3D 纹理），并加一条警告。没有不支持光追的机器，这条路径只验证过"出错 → 关闭"的逻辑，没有在真机上测过。

**调试画面**：Debug View 14 探针 GI（中灰表面 × 探针辐照度）、15 光追反射比值（`DEBUG.RT`）。

（§10 起见 `IMPLEMENTATION_2.md`。）
