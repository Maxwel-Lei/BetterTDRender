# M6 透明与折射：设计方案（草案 v2，2026-11-12）

状态：**设计阶段，未实现**（草案 v2：材质改为 BTDR 上的透明槽 + 拖拽）。实现顺序：先 B（M6a），再 A/C（M6b），最后 D（M6c）。实现后把定稿内容并入 `IMPLEMENTATION.md`（新 §9e）和 `USER_GUIDE.md`，本文件保留为设计记录。

## 0. 目标和原则

- 四种做法都做，**由用户选择**：
  - B：前景透明层（front-layer translucency）加屏幕空间折射。
  - A：前向半透明，按距离排序混合。
  - C：顺序无关透明 / 深度剥离。
  - D：硬件光追折射。
- 透明材质分成两类，各自用自己的做法，互不冲突：
  | 类别 | 例子 | 处理方式 |
  |---|---|---|
  | **折射类（Refractive）** | 玻璃、水、冰、宝石、车窗、镜片 | B，可选 D 增强 |
  | **混合类（Blended）** | 烟雾、全息投影、发光贴片、粒子、半透明塑料片 | A 或 C |
- **零配置能用**：用户在 TD 里怎么把 PBR MAT 设成透明（Alpha、Blending），BTDR 就怎么认。想精细控制（IOR、厚度、类别）时才需要额外设置。
- **不透明场景零开销**：没有透明物体时，所有透明相关节点都被 Switch 旁路，不计算。
- 保持 `GBUF.SHARED` 原则：折射类（B）的材质不读每帧变化的数据。混合类（A/C）必须读每帧数据，这部分开销只有启用时才有，在文档里说明。

## 1. 用户界面：新增 Transparency 页

| 参数 | 选项 / 默认 | 说明 |
|---|---|---|
| Transparency | On（默认） | 总开关；关闭时所有透明物体按不透明画（等于 0.5.x 的行为） |
| Refractive（列表） | 默认 0 条，+ / − 增删 | 折射类的透明槽：把几何体拖进槽里（§2.2） |
| Blended（列表） | 默认 0 条 | 混合类的透明槽（M6b） |
| Refraction Method | **Screen Space**（默认，B） / Hybrid（B + D 兜底） / Ray Traced（D） | 折射类物体用哪种算法。D 需要光追可用，不可用时自动退回 Screen Space 并提示 |
| Blend Method | **Sorted**（默认，A） / Order Independent（C，加权混合 OIT） / Depth Peeling（C，分层剥离） | 混合类物体的叠加方式，直接对应 Render TOP 的 Transparency 菜单 |
| Peel Layers | 3 | Depth Peeling 的层数 |
| Default IOR | 1.5 | 没有单独设置折射率的物体用这个值 |
| Absorption Distance | 1.0 m | 光在有色透明体里走多远衰减到"基础色"那么深（Beer-Lambert）。越小颜色越浓 |
| Soft Particles Distance | 0.1 m | 混合类物体靠近不透明表面时淡出的距离，避免硬交线 |
| Status（只读） | 例：`3 refractive, 2 blended` | |

Debug View 新增：Transparent Layer（前景透明层的基础色）、Thickness（测到的厚度）、Refraction Offset（折射偏移量）。

## 2. 材质：参数从哪来（重点）

### 2.1 约束

- 原生 MAT（包括 PBR MAT）**不能加自定义参数**（M0 已验证）。
- PBR MAT 有用的现成参数：
  - Alpha 页 `alphafront`（正面不透明度，默认 1）、`alphaside`、`alphamap`（Alpha 贴图）。
  - Common 页 `blending`（混合开关）、`alphatest` / `alphathreshold`（Alpha 测试）、`cullface`。
  - 基础色、粗糙度、法线贴图（折射也用得上）。
- PBR MAT **没有**：折射率（IOR）、厚度、吸收距离、透明类别、薄壁标志、色散。
- BTDR 的模型是"每个 Geometry COMP 一个材质"（`EXT.MIRROR`，不支持 Material SOP 逐面材质）。所以按 Geometry COMP 设参数，等价于按物体设材质参数。

### 2.2 三层来源，优先级从高到低

**第 1 层：BTDR 上的"透明槽"（拖拽，主要方式）**
Transparency 页有两个**列表参数**（TD 的序列参数 sequence，可以用 + / − 增删条目）：**Refractive** 和 **Blended**。每一条是一个"槽"：

| 槽里的参数 | 选项 / 默认 | 作用 |
|---|---|---|
| Geometry | （拖入 Geometry COMP） | **把几何体节点直接拖到这个框里**，和原生 Render TOP 的 Geometry 参数一样。也可以写路径模式，比如 `glass_*`，一条槽管一批物体 |
| Preset | **Glass** / Frosted Glass / Tinted Glass / Water / Ice / Crystal / Diamond / Acrylic / Custom | 选预设时自动填下面几项（只填 BTDR 自己的参数；材质颜色还是读 PBR MAT） |
| IOR | 1.5 | 折射率 |
| Roughness Override | -1（= 用 PBR MAT 的值） | 例如 Frosted Glass 预设设成 0.35，不用改原材质 |
| Thin Walled | Off | 开：当作薄壁（窗玻璃、肥皂泡、单面的平面），只着色、不偏移、不按厚度吸收 |
| Absorption Distance | 1.0 m | 吸收距离，越小颜色越浓 |
| Cast Shadow | **None** / Opaque | 是否投影。玻璃默认不投 |
| In Ray Tracing | Off | 是否进光追代理（D 和探针 GI 用） |

Blended 槽的参数：Geometry、Lit（受光 / 只自发光）、Soft Particles Distance、Cast Shadow。

- 用法：在 Transparency 页点 **+** 加一个槽，把玻璃杯的 Geometry COMP 拖进框里，选 Water 或 Glass，完成。
- 好处：
  - 符合 TD 用户已有的"拖节点到参数"习惯；所有透明设置集中在 BTDR 一处，一眼看全，不用一个个物体去翻。
  - 一个槽可以用通配符管一批物体，同一种玻璃不用重复设置。
  - 原生 Render TOP 完全不受影响。
- 被槽指定的物体即使不在 Geometry 参数的匹配范围里，也会被加入场景，相当于"拖进来就渲染"。
- 同一个物体出现在多个槽里时，以靠前的槽为准，Status 里给出提示。
- 已验证（TD 2025.33230）：COMP 可以加序列参数（`page.appendSequence`），块里可以放 COMP 类型的参数，`numBlocks` 增删条目；块内参数的名字是 `<序列名><序号><参数名>`（例如 `Refr2geo`），定义块参数时只写基础名。
- 实现：Refresh 时解析槽，把每个物体的槽参数用表达式绑定进内部材质的 `uTrans`，所以改槽参数立即生效；增删槽、换物体会自动 Refresh（同 Geometry 参数）。
- 更进一步（待验证）：把几何体节点直接拖到 `renderBTDR` 节点的方块上，自动新建一个 Glass 槽。TD 的 COMP 有 Drop Script（Drag/Drop 页），但它对"网络编辑器里拖到节点方块上"是否触发还要实测；不行就只保留拖到参数框的方式。

**第 2 层：从 PBR MAT 自动推断（零配置，没被任何槽指定的物体）**

| 源材质的状态 | 推断结果 |
|---|---|
| Common 页开了 `alphatest` | **Opaque + 镂空**：G-Buffer 里按阈值 discard（树叶、铁丝网）。这是顺带补上的另一个缺口 |
| `alphafront` < 1，或挂了 `alphamap`，且**没有**开 `blending` | **Refractive**，IOR = 全局默认值 |
| 开了 `blending` 且挂了 `alphamap` | **Blended**：贴图决定形状的半透明，例如烟雾贴片、粒子 |
| 开了 `blending` 但没有 Alpha 贴图 | **Refractive**。整块均匀的透明体通常是玻璃类；想要不折射的效果，把它拖进 Blended 槽 |
| 其他 | Opaque |

PBR 参数在透明物体上的含义：
- **不透明度 α**（`alphafront` × Alpha 贴图）：0 = 完全透明的玻璃，1 = 不透明。中间值 = 透明体表面有一层漫反射的"雾面涂层"（有色塑料、蒙了灰的玻璃）。
- **基础色**：透明体内部的颜色。折射类按吸收距离换算成吸收系数，物体越厚颜色越深；薄壁和混合类直接当染色用。
- **粗糙度**：同时控制表面反射的模糊程度和**透射的模糊程度**，也就是磨砂玻璃。
- **法线贴图**：扰动折射方向。水面波纹、压花玻璃都靠它。
- **金属度**：透明物体上忽略（金属不透光）。
- **自发光**：照常叠加，用来做发光玻璃管、全息投影。

**第 3 层：全局默认值**：自动推断出来的折射类物体用 Transparency 页的 Default IOR、Absorption Distance。

### 2.3 材质库（M6a 一起交付）

槽的 Preset 已经覆盖了常见的折射率和粗糙度。另外在 Palette 里提供 `BTDR_MaterialLibrary.tox`：一组调好的 PBR MAT（基础色、粗糙度、法线贴图都配好），和预设一一对应：清玻璃、磨砂玻璃、茶色玻璃、水、冰、钻石、彩色亚克力、全息投影（Blended + 自发光）、烟雾贴片（Blended）。用法：把材质拖给物体，再把物体拖进对应预设的槽。

### 2.4 否决的方案

| 方案 | 否决原因 |
|---|---|
| 在每个 Geometry COMP 上加一页 BTDR 参数（草案 v1 的第 1 层） | 设置分散在各个物体上，看不出场景里哪些是透明的；同一种玻璃要逐个设置。透明槽集中、可批量，更直观 |
| 专用的 BTDR 材质 COMP（内包一个 PBR MAT，外面挂参数） | 用户要学新节点；Geometry COMP 的 Material 参数得指向 COMP 里面的 MAT，路径别扭；原生渲染兼容但不直观。留作以后的"材质复用"方案 |
| 用材质名字或 OP 标签（tags）写参数 | 隐式，用户看不到、容易写错 |
| BTDR 里放一张"路径 → 参数"的覆盖表 | 适合大批量物体，但离物体太远；以后需要时可以加成第 0 层 |

## 3. 方案 B：前景透明层 + 屏幕空间折射（M6a，先做）

成熟引擎的对应做法：UE5 Lumen 的 Front Layer Translucency（给最前面一层透明表面单独存 G-Buffer）+ Unity HDRP 的屏幕空间折射（折射模型 Thin / Sphere / Box、按粗糙度取模糊背景的 color pyramid）。BTDR 比 HDRP 多一步：用背面渲染**实测厚度**，HDRP 要手填。

### 3.1 管线

```
不透明：gbuffer → … → composite ─────────────────────────────┐
透明（折射类）：scene/t* ─▶ tgbuffer (Render TOP, cam_jit, 5 个颜色缓冲) ─┐ │
                  scene/t* ─▶ tback   (Render TOP, 剔除正面, 只要位置和法线) ─┤ │
composite ─▶ scene_pyr（背景模糊链：½ … 1/32） ────────────────────────────┤ │
                                                      refract (全屏 GLSL) ◀┘ │
                                    trans_src (Switch: composite / refract) ◀┘
trans_src ─▶ [M6b 的混合类通道] ─▶ fog_apply ─▶ taa ─▶ …（以后不变）
```

- 镜像：`EXT.MIRROR` 按 2.2 的结果分流。折射类物体建成 `scene/t<i>`，不进 `gbuffer`（几何体模式改成 `scene/g*`）、不进阴影（除非 Cast Shadow = Opaque）、不进光追代理（除非 In Ray Tracing）。
- 材质：**复用 `gbuffer.frag`**，多写第 5 个输出 RT4（IOR、吸收距离、薄壁、不透明度）。不透明 G-Buffer 只有 4 个颜色缓冲，多写的 RT4 被丢弃，不影响它。新增的 uniform `uTrans` 用表达式绑定到对应透明槽的参数和 PBR MAT 的 Alpha 页，**不读每帧数据**。同一个源材质用在不同槽的物体上时，镜像材质按（源材质，槽）各建一份。
- `tback`：同样的几何体和材质，Render TOP 的 Cull Face = Front Faces，得到"最远的背面"的位置和法线。厚度 = 背面视深 − 正面视深。
- 与不透明物体的遮挡在 `refract` 里逐像素判断：透明表面的视深大于不透明表面就忽略；背面深度用不透明表面截断（插进桌面的玻璃杯）。
- `scene_pyr`：背景模糊链。第一版用 GLSL TOP 生成带 mipmap 的 HDR 图，用 `textureLod` 取；如果盒式 mip 在磨砂玻璃上不够平滑，改成 Bloom 那样的 13 点下采样链（已有代码）。

### 3.2 `refract` 的着色（每个透明像素）

1. 读前景层：位置 P、法线 N、粗糙度 r、基础色、IOR η、吸收距离、薄壁、不透明度 α。V = 指向相机。
2. **菲涅尔**：F0 = ((η − 1)/(η + 1))²，Schlick 近似，粗糙度修正和现有 `EnvBRDFApprox` 一致。
3. **透射方向**：
   - 薄壁：出射方向 = 入射方向，只按法线做极小的偏移（窗玻璃本来就几乎不偏）。
   - 实心：T1 = refract(−V, N, 1/η)，沿 T1 走"厚度"到背面，再用背面法线做第二次折射 T2 = refract(T1, −Nb, η)。遇到全内反射时沿反射方向继续，这就是 HDRP Sphere/Box 模型，但厚度是实测的。
4. **找背景**：从出射点沿 T2 走"到不透明表面的距离"（用背景深度估算），投影到屏幕取 `scene_pyr`；取哪一级 mip 由粗糙度和走的距离决定（磨砂）。点落在屏幕外或背景深度不连续时，按 Refraction Method：Screen Space 退到环境贴图 `envRadiance(T2, r)`；Hybrid 用 D 的结果。
5. **吸收**：σ = −ln(基础色) / 吸收距离，透射率 = exp(−σ × 厚度)。薄壁直接乘基础色。
6. **表面项**：环境镜面（`envRadiance(R, r)` × 镜面遮蔽）+ 太阳的 GGX 高光（查同一张阴影图）+ 自发光。不透明度 α 部分按普通的漫反射表面算光照（复用 `lightingTerms` 的漫反射分支）。
7. **合成**：结果 = (1 − F) × [(1 − α) × 透射 × 吸收 + α × 漫反射] + F × 反射 + 高光 + 自发光。
8. 第 2 个输出：合并后的位置（透明表面在前就用它），给 fog_apply、TAA、景深、运动模糊用，让玻璃的轮廓有正确的深度。

### 3.3 和其他功能的配合

| 功能 | 处理 |
|---|---|
| 体积雾 | `fog_apply` 改读合并后的深度：雾作用到玻璃表面为止。玻璃后面那一段的雾已经在背景图里了，所以不会重复 |
| TAA | 用合并后的位置做重投影。玻璃上透过去的背景会跟着玻璃动（略软，可接受），玻璃轮廓不拖影 |
| SSR / SSGI / AO | 仍只基于不透明 G-Buffer。玻璃本身会出现在 SSR 读的上一帧画面里，所以不透明物体能"映出"玻璃 |
| 光追反射 / 探针 | 玻璃默认不在代理里（不挡光）。In Ray Tracing 打开后才进 |
| 阴影 | 默认不投影；Cast Shadow = Opaque 时进阴影的投影物体列表 |
| Debug View | 新增 3 个；原有的 G-Buffer 视图仍只显示不透明层 |
| Quality Low | `tback` 和 `scene_pyr` 用半分辨率；实心物体的第二次折射省掉（按薄壁加平均厚度近似） |

### 3.4 已知限制（写进使用手册）

- 只处理**最前面一层**透明表面：玻璃后面的另一块玻璃看不见。多层透明要等 D（Ray Traced）。
- 互相穿插或嵌套的透明物体（杯子里的水）会算错：厚度是所有透明物体背面合并的结果。
- 折射只能读到屏幕里有的东西；屏幕外退到环境贴图或 D。
- 没有焦散、没有色散（色散留作以后的选项：RGB 三个 IOR 各取一次）。
- 玻璃不投彩色阴影。

### 3.5 预估开销（1080p，5080 Laptop，待实测）

- 透明物体占屏 20% 时：GPU `tgbuffer` + `tback` 约 0.1 ms，`scene_pyr` 约 0.05 ms，`refract` 约 0.1–0.2 ms。
- CPU：多 4–5 个节点，约 +0.1–0.15 ms。
- 没有透明物体：0。

## 4. 方案 A / C：前向混合通道（M6b）

给**混合类**物体（烟雾、粒子贴片、全息）用，接在 `refract` 之后。

- 镜像：混合类物体建成 `scene/b<i>`，用前向材质 `forward.vert/frag`（GLSL MAT）：
  - 简化光照：环境辐照度 + 太阳 × 阴影 + 自发光，可选不受光（纯自发光）。
  - 输出预乘 alpha。
  - 读 `uB` 数组，所以**每帧都要重新计算**（每个混合类材质约 0.05 ms CPU）。这是 A/C 的固有代价，写进手册。
- `blend` Render TOP：几何体 `scene/b*`，相机 `cam_jit`，Transparency 菜单 = Blend Method（Sorted → sortedblending，Order Independent → orderind，Depth Peeling → depthpeel + Peel Layers）。
- 遮挡：材质里采样合并深度（不透明 + 前景透明层），在后面的像素丢弃；离不透明表面很近时按 Soft Particles Distance 淡出（**软粒子**）。
- 合成：`blend` 预乘叠加到 `trans_src` 上，再进体积雾和 TAA。
- 限制：混合类物体在玻璃后面时，按玻璃的透射率压暗、但**不折射**（只有前景一层参与折射，和 UE5 的排序限制同类）。
- 粒子：TD 的粒子 POP / Particle SOP 加实例化，可以直接用混合类材质画成柔和的发光贴片。音频粒子场景就能用"软粒子"了。

## 5. 方案 D：硬件光追折射（M6c）

- `rt_refr`（GLSL POP，和 `rt_refl` 同一套）：1/4 分辨率，从前景透明层发折射光线，**在代理里真的穿过玻璃**：进、出各折射一次，最多 4 次反弹，遇到全内反射就反射。命中不透明物体后用 surface cache 着色（同现有光追反射）。
- 需要的数据：玻璃要在代理里（In Ray Tracing），`rt_mat` 表加一列"透明 / IOR"。
- 时间累积（同 `ACCUM.RT`），结果交给 `refract`：
  - **Hybrid**：屏幕空间找不到背景的像素用光追结果。
  - **Ray Traced**：全部用光追结果，能看到多层玻璃和画面外的东西。
- 局限：代理减面、命中点只有平均色，所以光追折射里的画面偏模糊、偏平。近处、清晰的折射仍是屏幕空间的更好，所以默认 Hybrid 优于纯 Ray Traced。

## 6. 分期和验收

| 阶段 | 内容 | 验收 |
|---|---|---|
| **M6a** | 材质三层来源（透明槽 + 拖拽、PBR 推断、Alpha 测试镂空）、B 全套、Transparency 页、3 个 Debug View、材质库 tox | 测试场景：清玻璃球、磨砂玻璃板、有色水块、薄窗玻璃、插进地面的玻璃杯；回归测试新增 `TEST.M6`（无透明时旁路、折射偏移方向正确、厚度合理、吸收单调、无 NaN）；没有透明物体时 demo 场景性能不变（A/B 对比画面差为 0） |
| **M6b** | A/C 前向混合通道、软粒子 | 烟雾贴片、全息投影、粒子；三种 Blend Method 都出图；排序错误只在文档写明的情况下出现 |
| **M6c** | D 光追折射、Hybrid | 多层玻璃、画面外物体透过玻璃可见；不支持光追时自动退回并提示 |

uniform 槽位：40 个已用满，M6 需要约 3 个（折射全局参数、混合参数、光追折射参数）。届时把数组扩到 48（`NSLOT`、`common.glsl`、测试的 4 × 40 一起改）。
