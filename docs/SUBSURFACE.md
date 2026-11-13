# 0.8 次表面散射（Subsurface Scattering，SSS）：设计方案（草案 v1，2026-11-14）

状态：**方案，未实现**。实现后，记录写进 `IMPLEMENTATION_2.md` 和 `USER_GUIDE.md`，本文件保留为设计记录。

## 0. 目标和原则

- **术语**：次表面散射，英文 Subsurface Scattering，简称 SSS。它模拟光钻进半透明材质内部、散开后从附近别的位置射出的现象。
  - 效果：皮肤边缘透红，玉、蜡、大理石、牛奶看起来“软”，树叶和耳朵背光时透亮。
  - 和玻璃的区别：BTDR 现有的折射槽只做**吸收**（光直线穿过、被染色），不会在材质内部散开。
- 对应 UE5 的两种着色模型，都做：
  | 成分 | UE5 对应 | 管什么 | 例子 |
  |---|---|---|---|
  | **屏幕空间散射**（Screen-Space Diffusion） | Subsurface Profile（Burley 归一化扩散） | 正面受光时，光在表面下横向扩散，阴影边缘和细节变软、带颜色 | 皮肤、玉、蜡、大理石、牛奶、肥皂 |
  | **透射**（Transmission） | Subsurface / Two Sided Foliage | 背光时光从物体背面透过来 | 耳朵、鼻翼、指缝、蜡烛顶、树叶、纸、灯罩 |
- **零开销原则**（和透明一样）：场景里没有 SSS 物体时，新节点全部被 Switch 旁路，画面和 0.7.6 逐像素相同。
- **不加 Render TOP**：M6a 实测一个额外的 Render TOP 约 0.3 ms CPU，所以 SSS 只加全屏 GLSL TOP。档案编号塞进现有 G-Buffer 的空闲通道。
- 保持 `GBUF.SHARED`：G-Buffer 材质只绑定静态表达式（档案编号），不读每帧数据。
- 预算：1080p High，SSS 物体占画面约 30% 时，GPU 增加不超过 0.5 ms，CPU 增加不超过 0.1 ms。

## 1. 用户界面：新增 Subsurface 页

| 参数 | 选项 / 默认 | 说明 |
|---|---|---|
| Subsurface | On | 总开关；关闭后 SSS 物体按普通不透明材质画 |
| Quality | **Auto**（跟随渲染器的 High / Low）/ High / Low | High：全分辨率，每个方向 15 个采样；Low：半分辨率，每个方向 9 个采样 |
| Scatter Scale | 1.0 | 所有档案的散射半径一起乘这个数。场景单位不是米时用它校正（以后统一到全局 Scene Scale） |
| Transmission | On | 透射总开关 |
| Subsurface Objects（列表） | 默认 0 条，+ / − 增删 | SSS 槽，最多 8 条（§2） |
| Status（只读） | 例：`2 subsurface profiles, 5 objects` | 槽超过 8 条、物体同时在折射槽和 SSS 槽里、几何体找不到时，在这里提示 |

Debug View 新增 3 项：
- Subsurface Profile：按档案编号上色。
- Subsurface Irradiance：模糊前和模糊后左右对比，用来看散射范围。
- Transmission：只显示透射项。

## 2. 材质：SSS 槽（和透明槽同一套用法）

TD 的 PBR MAT 没有任何次表面参数（也不能加自定义参数，M0 已验证），所以和透明一样，在 BTDR 上用**列表参数（sequence）**设置。

| 槽里的参数 | 选项 / 默认 | 作用 |
|---|---|---|
| Geometry | 拖入 Geometry COMP，或写路径模式（如 `skin_*`） | 指定哪些物体用这个档案 |
| Preset | **Skin** / Jade / Wax / Marble / Milk / Soap / Leaf / Paper / Custom | 选预设时自动填下面几项 |
| Scatter Color | 例：皮肤 (0.90, 0.35, 0.20) | 散射颜色。哪个通道的值大，那个颜色的光在材质里走得远（皮肤的红光走得最远，所以阴影边缘发红） |
| Scatter Radius | 例：皮肤 0.012 m | 光在材质里平均横向扩散的距离（米）。乘以 Scatter Color 得到每个颜色通道的扩散距离 |
| Strength | 1.0 | 0 = 不散射，1 = 完全按档案散射。用来做“有点透”的材质 |
| Texture Detail | 0.5 | 贴图细节保留多少。0 = 先乘贴图再模糊（贴图细节被糊掉），1 = 模糊后再乘贴图（细节最清晰但颜色偏平）。对应 UE 的 pre-/post-scatter |
| Transmission Color | 例：皮肤 (1.0, 0.25, 0.10) | 背光透过来的光的颜色，黑色 = 不透光 |
| Transmission Strength | 1.0 | 透射强度 |
| Thin | Off | 开 = 薄片模式（树叶、纸、灯罩）：不做屏幕空间模糊，只算透射，厚度用下面的 Thickness，不从阴影图测量。对应 UE 的 Two Sided Foliage |
| Thickness | 0.002 m | 只在 Thin 打开时用 |

- 用法：在 Subsurface 页点 **+**，把模型的 Geometry COMP 拖进框里，选 Skin / Jade / Wax，完成。颜色、粗糙度、法线贴图仍然读 PBR MAT。
- 改槽参数立即生效（每帧通过 uniform 数组读取，不需要 Refresh）；增删槽、换物体时自动 Refresh（同 Geometry 参数）。
- 同一个物体出现在多个 SSS 槽里，以靠前的槽为准。同时在折射槽和 SSS 槽里，折射优先，Status 提示。
- 金属度会削弱 SSS（按 1 − metallic 缩放），Constant MAT（不受光）忽略 SSS。
- 实例化几何体、粒子：档案按材质绑定，实例自动继承，不用额外处理。

### 2.1 预设表（初值，实现时按测试图调）

| Preset | Scatter Color | Radius | Transmission Color | Thin |
|---|---|---|---|---|
| Skin（皮肤） | 0.90, 0.35, 0.20 | 0.012 m | 1.00, 0.25, 0.10 | Off |
| Jade（玉） | 0.45, 0.95, 0.60 | 0.020 m | 0.30, 0.90, 0.45 | Off |
| Wax（蜡） | 1.00, 0.75, 0.45 | 0.015 m | 1.00, 0.60, 0.30 | Off |
| Marble（大理石） | 0.95, 0.93, 0.88 | 0.008 m | 0.80, 0.78, 0.72 | Off |
| Milk（牛奶 / 奶油） | 1.00, 0.97, 0.90 | 0.025 m | 1.00, 0.95, 0.85 | Off |
| Soap（肥皂） | 0.95, 0.90, 0.95 | 0.010 m | 0.90, 0.85, 0.90 | Off |
| Leaf（树叶） | — | — | 0.55, 0.85, 0.20 | On，0.0005 m |
| Paper（纸 / 灯罩） | — | — | 1.00, 0.95, 0.85 | On，0.0003 m |

预设的半径按真实尺寸（米）给。模型比例不对时（比如一个 10 单位高的人头），用 Scatter Scale 校正，不改预设。

## 3. 管线

```
gbuffer (RT3.a = 2 + 档案编号) ─▶ composite ──buf0: 完整光照────────────────┐
                                      └──buf1: 可散射的辐照度 | 档案编号 ─┐   │
                                                         sss_h（横向模糊）◀┘   │
                                                         sss_v（纵向模糊 + 合成）◀┘
                         sss_src (Switch: composite / sss_v) ─▶ scene_pyr / refract ─▶ fog_apply ─▶ taa ─▶ …（以后不变）
```

### 3.1 G-Buffer：档案编号放在 RT3.a

- 不透明 G-Buffer 的 RT3.a 现在写的是不透明度，但不透明层里没有任何 shader 读它：composite、lighting、debug 都只读 `.rgb`，只有透明层 `tgbuffer` 的 RT3.a 被 refract 使用。
- 新编码：`a ∈ [0, 1]` 仍是不透明度；`a = 2 + k` 表示 SSS 档案 k（k = 0..7）。16 位浮点可以精确存这些整数。透明层不会被分配 SSS 档案，所以不冲突。
- `gbuffer.frag` 新增一个静态 uniform `uSSS`（x：档案编号，−1 = 无），由 Refresh 用表达式绑定到槽，和 `uTrans` 一样不读每帧数据。
- 实现前要验证的一点：确认 `mblur`、`taa` 和所有 Debug View 都没有读不透明层的 RT3.a（目前 grep 结果是没有）。

### 3.2 composite：分出“可散射的部分”

- composite 的第 2 个输出（只在场景里有 SSS 槽时才打开 `numcolorbufs = 2`，否则仍是 1 个，没有额外开销）：
  - rgb：**辐照度** = 太阳漫反射 + 环境漫反射（或探针 GI）+ Ambient Light + SSGI 反弹 + 透射，**不乘基础色**；
  - a：档案编号（非 SSS 像素为 0）。
- buf0 保持完整光照不变，所以 SSS 只是对它做修正。
- `lightingTerms` 需要把太阳的漫反射单独输出一份：新增一个带额外 out 参数的版本，`lighting.frag`（Debug View 用）继续用旧版本。
- 高光、反射（SSR、光追反射）、自发光不参与散射，保持清晰，这是 SSS 看起来真实的关键。

### 3.3 sss_h / sss_v：可分离的屏幕空间散射

- 两个全屏 GLSL TOP，先横向后纵向。这是 Jimenez 的可分离 SSS 结构，核函数用 Burley 归一化扩散（UE5 Subsurface Profile 用的同一个模型），每个颜色通道一个扩散距离：
  `R(r) = (e^(−r/d) + e^(−r/3d)) / (8π·d·r)`，d = Scatter Radius × Scatter Color × Scatter Scale。
- 采样：
  - 采样点按 R(r) 做重要性采样，High 每个方向 15 个，Low 9 个（半分辨率）。
  - 屏幕上的步长 = 世界半径 ÷ 该像素的视深换算成像素，最大 64 像素（太近时限制住，不会全屏糊）。
- 防漏光：
  - 采样点的档案编号不同，就不采；
  - 视深差超过半径的几倍，权重按高斯衰减（Jimenez 的 follow-surface）。
  - 被拒绝的采样用中心像素的值代替，所以能量守恒，边缘不会变暗。
- 非 SSS 像素在第一行就退出，开销只和 SSS 物体占画面的比例有关。
- 合成（在 `sss_v` 里）：
  `结果 = buf0 + 基础色系数 × (模糊后的辐照度 − 原辐照度) × Strength`
  - 基础色系数按 Texture Detail 在“模糊前乘贴图”和“模糊后乘贴图”之间插值（UE 的做法是两边各开平方）。
  - 只修正漫反射这一部分，高光原样保留。
- 噪声：采样旋转不随帧变化（可分离结构不需要），TAA 照常处理。

### 3.4 透射（在 composite 里算，结果并进辐照度，再参与模糊）

- **厚度怎么来**：太阳阴影图存的是“从光源到第一个表面的线性距离”（`LIGHT.SHADOW`）。对 SSS 像素：
  厚度 = 该点到光源平面的距离 − 阴影图在该点处存的距离。
  这正是光从物体背面进入、走到这个点的路程。UE 的 Subsurface 着色模型也用阴影图这样估厚度。
  - 用 4 个采样做 PCF 平均，避免硬边。
  - 厚度 0–3 cm 的部分是透光的主要来源（耳朵、指缝、玉的薄边）。
- **透射量** = Transmission Color × exp(−厚度 / (d × 3)) × 太阳颜色 × 强度 × 包裹项 `saturate(−N·L × 0.5 + 0.5)²` × Transmission Strength。
- **薄片模式**（Thin）：厚度用槽里的 Thickness，不查阴影图；另外加一份背面的环境光（`envIrradiance(−N)` × Transmission Color），树叶在阴天下也透亮。
- **局限**：阴影图分不清“自己的背面”和“别的遮挡物”。玉镯后面隔着一只手时，厚度会被算成“手到玉镯”的距离而偏大，透射变弱。这一般是对的方向（被挡住就不透光），UE 有同样的近似。

## 4. 和现有功能的配合

| 功能 | 处理 |
|---|---|
| 透明 / 折射 | SSS 在 `scene_pyr` 之前完成，所以透过玻璃看到的 SSS 物体也是散射过的。SSS 物体不能同时是折射物体（折射优先） |
| 体积雾 | 在 SSS 之后，不受影响 |
| TAA | 在 SSS 之后，正常重投影 |
| SSR | 读的是上一帧的最终画面，反射里的 SSS 物体也是散射过的 |
| 光追反射 / 探针 GI | 代理里只有平均色，不做散射（反射里的皮肤会稍硬，可以接受） |
| SSGI 反弹光 | 包含在辐照度里，一起被散射 |
| 阴影 | SSS 物体照常投影，透射读的就是这张阴影图 |
| Shell 版（BTDR_Shell） | Subsurface 页的列表参数要加进 `SyncShell` 的序列同步，和 Refr 一样 |
| Debug View | 原有视图不变，新增 3 项（§1） |
| Quality Low | 半分辨率模糊、9 个采样、透射只用 1 个阴影采样 |

## 5. uniform 槽位

现在 44 槽（0–40 已用，41–43 空闲）。扩到 **68**（`NSLOT`、`common.glsl`、测试里的 4 × 44 一起改）：

| 槽 | 内容 |
|---|---|
| 41 `uSSSG` | x 总开关，y Scatter Scale，z 采样数，w 透射开关 |
| 44 + 3k | 档案 k：rgb Scatter Color × Radius（每通道扩散距离 d），w Strength |
| 45 + 3k | 档案 k：rgb Transmission Color × Strength，w Thin（1 = 薄片） |
| 46 + 3k | 档案 k：x Texture Detail，y Thickness（薄片用），zw 空 |

k = 0..7，占 44–67。42、43 留空。

## 6. 已知限制（写进使用手册）

- 屏幕空间方法只能散射画面里看得到的光：
  - 物体背面、画面外的光不会散过来；
  - 镜头贴得很近（散射半径大于 64 像素）时会被限制，显得偏硬。
- 透射只来自那一盏平行光（和 BTDR 现在只支持一盏平行光一致）。以后支持多光源时一起扩展。
- 没有单独的厚度贴图（UE 的 Opacity / Thickness Map）。如果测试里玉器、蜡烛不够理想，0.8c 再加一个可选的 Thickness Map 参数（TOP）。
- 反射、光追里的 SSS 物体不散射。
- 场景尺度依赖：预设按米给，模型尺寸不对时必须调 Scatter Scale。

## 7. 分期和验收

| 阶段 | 内容 | 验收 |
|---|---|---|
| **0.8a** | SSS 槽和 8 个预设、G-Buffer 编号、composite 第 2 输出、`sss_h` / `sss_v`、Subsurface 页、2 个 Debug View、Shell 同步 | 见下方 0.8a 验收 |
| **0.8b** | 透射：阴影图测厚度、薄片模式、Transmission Debug View | 见下方 0.8b 验收 |
| 0.8c（看情况） | 可选的 Thickness Map、Scene Scale 全局参数 | 由 0.8a/b 的测试图决定是否需要 |

**0.8a 验收**
- 测试场景：玉兔（Stanford Bunny + Jade）、蜡块、大理石球、贴图人头模型（找 CC0 的扫描模型，皮肤）。
- 新增 `tests/m8_tests.py`，检查：
  - 没有 SSS 槽时旁路，和 0.7.6 平均差为 0；
  - 均匀受光的平面上散射前后亮度差小于 2%（能量守恒）；
  - 档案编号边界和深度断层处不漏光（相邻的非 SSS 物体亮度不变）；
  - 阴影边缘在 SSS 物体上变宽，且红通道变得比蓝通道宽（皮肤）；
  - 没有 NaN。
- 性能：1080p High，SSS 占画面 30%，GPU 增加不超过 0.5 ms，CPU 增加不超过 0.1 ms；无 SSS 时为 0。

**0.8b 验收**
- 测试场景：背光的手掌或耳朵、阳光下的树叶平面、台灯灯罩、背光的玉片。
- 检查：
  - 透射随厚度单调减小；
  - 正面光照下透射约为 0；
  - 薄片在阴天环境下仍透亮。
- 性能：透射在 composite 里每个 SSS 像素约 4 次阴影图读取，GPU 增加不超过 0.1 ms。

**每个阶段都交付**：
- 和不开 SSS 的对比图；
- 回归测试：m1 39 项、m7 13 项、m5 7 项全过；
- `USER_GUIDE.md` 新增一节，`IMPLEMENTATION_2.md` 更新变更记录和踩坑；
- 同步更新项目文档、Palette、示例 tox 和 Shell 版。

## 8. 否决的方案

| 方案 | 否决原因 |
|---|---|
| 给不透明 G-Buffer 加第 5 个颜色缓冲存 SSS 参数 | 1080p 每帧多写读约 16 MB；RT3.a 本来就空着，存一个编号就够，参数都放在 uniform 里 |
| 非可分离的 Burley 重要性采样（UE5 现在的默认实现） | 质量略好，但每像素 32–64 个采样，加上逐帧旋转靠 TAA 去噪，开销约是可分离版的 2–3 倍；BTDR 的预算放不下。可分离版在皮肤上的差别很小 |
| 纹理空间扩散（Texture-Space Diffusion，早期 NVIDIA 人脸 demo） | 需要每个物体一张光照贴图和 UV 展开，TD 场景里做不到通用 |
| 光追随机游走（Random Walk） | 最准确，但实时开销远超预算；只在离线路径追踪里合理 |
| 只做包裹光照（Wrap Lighting）的廉价近似 | 只能让暗部变亮，做不出颜色渗透和细节变软；保留为 Low 档的退路，不作为主方案 |
