# BetterTDRender（BTDR）使用手册

版本 0.9.1。BetterTDRender 是 TouchDesigner 里的一个渲染节点 `renderBTDR`，用法和原生 Render TOP 一样：
填上相机、几何体、灯光就出画面。区别是它内部走延迟渲染管线，画面接近虚幻引擎 5 的默认效果：

- PBR 材质（直接用原生 PBR MAT）、软阴影、摄影棚或 HDRI 环境光照、ACES 色调映射
- 时间性抗锯齿（TAA）、Bloom（泛光）、自动曝光、景深、运动模糊
- 环境遮蔽（AO）、反弹光、反射、体积雾
- 硬件光追（简化版 Lumen）：探针全局光照和光追反射，画面外、被挡住的东西也参与反射和间接光
- 透明与折射（0.6.0）：玻璃、水、冰、宝石、磨砂玻璃，真实的折射、按厚度变深的颜色和菲涅尔反射；Alpha 测试镂空
- 光追折射（0.7.0）：用硬件光追穿过玻璃找背景，玻璃后面的玻璃、画面外的物体都能透过来

想了解内部实现，看 `IMPLEMENTATION.md`、`IMPLEMENTATION_1b.md` 和 `IMPLEMENTATION_2.md`（面向开发者）。

## 1. 运行环境

| 项目 | 要求 |
|---|---|
| TouchDesigner | 2025.33230 或更新 |
| 系统 | Windows |
| 显卡 | 推荐 RTX 4060 Laptop（Quality = High），最低 RTX 2060（Quality = Low）。硬件光追需要支持光线查询（Ray Query）的显卡：NVIDIA RTX 20 系及以上；不支持时自动关闭，其余功能照常 |

## 2. 五分钟上手

发布包里有两个文件：`BTDR.tox`（渲染节点本身）和 `BTDR_Example.tox`（做好的示例网络）。

### 2.1 先看示例

把 `BTDR_Example.tox` 拖进任意网络，进入它，看里面的 `OUT`。这是一个摆好的小场景：光滑地面、5 个从镜面到哑光的球、一面红墙、一个拱门、一个发光方块，相机左右摆动。
可以看到红墙把颜色"染"到地面上（反弹光），镜面球里映出画面外的东西（光追反射），发光方块周围的光晕（Bloom）。
示例网络里的 `README` DAT 有简短说明；把这个网络当成模板，换成你自己的模型即可。

### 2.2 从空网络开始

1. 在空网络里放：一个 **Camera COMP**（`cam1`，Translate Z 设成 5）、一个 **Light COMP**（`light1`，Light Type 选 **Distant**，Rotate X −45、Y 30）、
   一个 **Geometry COMP**（`geo1`，自带一个圆环）和一个 **PBR MAT**，把 PBR MAT 拖到 `geo1` 的 Material 参数上。
2. 把 `BTDR.tox` 拖进这个网络，得到 `renderBTDR1`。（装好之后也可以在 Palette 面板 Alt+L 里找 **My Components → BTDR → BTDR**，见 §2.3。）
3. 在 `renderBTDR1` 的输出接一个 Null TOP，打开它的预览。完成。

不用填任何参数：Camera、Geometry、Lights 的默认值是 `cam1`、`*`、`*`，会自动找到同一网络里的相机、所有 Geometry COMP 和平行光。
路径的写法和原生 Render TOP 一致：相对于 `renderBTDR` 所在的网络，也可以写绝对路径或用通配符。
材质照常用原生 **PBR MAT** 赋给 Geometry COMP，不需要任何专用材质。

**封面和加载画面（0.7.4）**：刚拖进网络或打开工程时，第 1 个输出先显示 TD学长 的封面。
- 还没找到相机时，封面下方写着 “Waiting for a camera”，节点每半秒检查一次，Camera 参数指向的相机一出现就自动开始。
- 找到相机后显示约 1 秒的加载动画（Logo 上有一道扫光），这段时间渲染在后台准备（编译着色器、填满时间累积），然后自动切换成渲染画面。
- 之后改参数、刷新场景都不会再出现封面；下次打开工程会再显示一次。第 2、3 个输出（HDR、深度）不受影响。
- 时间轴暂停时拖入不显示加载动画，直接出渲染画面（0.7.5）。
- 不想要封面（比如输出直接接到演出窗口）：关掉 **Info 页 → Cover While Loading**。
- 第一次把 BTDR 拖进一个工程时会弹出作者和联系方式的窗口，只弹一次：弹过之后 Info 页的 **Show At Startup (once)** 自动关掉，保存过的工程再打开不会再弹（0.7.5）；同一次 TD 运行里最多弹一次。之后可以在 **Info 页**点 **About / Contact...** 再打开。

接下来通常会调的几项：
- 想要天空和真实的环境反射：**Environment 页**换成 HDRI（§3 Environment 页）。
- 画面太亮 / 太暗：**Grade 页 → Exposure**。
- 显卡比较弱：**Render 页 → Quality = Low**。

### 2.3 安装到 Palette（可选）

把 `BTDR.tox` 复制到 `文档/Derivative/Palette/BTDR/BTDR.tox`（没有就新建 `BTDR` 文件夹），重启 TD 后 Palette 的 My Components 里就有 BTDR，以后从这里拖。
BTDR.tox 是自包含的，不引用任何外部文件，拖进任何工程都能用。

Palette 的 BTDR 文件夹里还有带版本号的旧版本（如 `BTDR_0.7.6.tox`），不带版本号的 `BTDR.tox` 永远是最新版；新版有问题时可以换回旧版对比。

### 2.4 什么时候要点 Refresh Scene

`renderBTDR` 在内部给每个几何体建了一份"镜像"。下面这些改动是实时跟随的，**不用**刷新：

- 移动、旋转、缩放几何体、相机、灯光
- 改 PBR MAT 的任何颜色、数值、贴图
- 改灯光的颜色和 Dimmer
- 改实例化（Instancing）参数

下面这些也不用刷新，节点每半秒检查一次，有变化自动刷新（0.7.4 / 0.7.5）：

- 新增、删除、改名相机 / Geometry COMP / 灯光（包括 Ambient Light、Environment Light）
- 开关 Geometry COMP 的 Render 标志
- 给几何体换了另一个材质节点
- 在 Geometry COMP 里换了 Render 标志所在的 SOP / POP

只有这一种改动之后要点一次 **Render 页 → Refresh Scene**：

- 改了材质的颜色或贴图，并且想让光追（Ray Tracing 页）里的反射和反弹光也跟上（光追代理的颜色在 Refresh 时取一次平均值）

改 Camera、Geometry、Lights 这三个参数本身会自动刷新。

## 3. 参数

### Render 页

| 参数 | 作用 |
|---|---|
| Camera | 相机。只支持透视相机 |
| Geometry | 几何体，通配符匹配 Geometry COMP |
| Lights | 灯光。当前只用一盏：优先取第一盏 Distant 类型的 |
| Refresh Scene | 重新解析上面三个参数并重建内部镜像 |
| Status | 只读。正常时显示 `OK: N geometry`；有问题时显示警告条数和第一条内容 |
| Resolution | 输出分辨率，默认 1920×1080 |
| Quality | High / Low / Custom。High 和 Low 会接管性能相关的参数（阴影图分辨率；景深、运动模糊、AO、反射的采样数；Low 档 AO / 反射用半分辨率；体积雾的格子数；光追的探针数和反射分辨率；Bloom 的级数） |
| Debug View | 查看中间结果：基础色、法线、粗糙度、金属度、材质 AO、自发光、深度、直接光、环境漫反射、环境镜面、屏幕空间 AO（白 = 不遮挡）、反弹光（SSGI）、反射（SSR）、Probe GI（探针算出的入射光，打在中灰表面上的样子）、Traced Reflections（光追反射比环境反射亮还是暗：灰 = 一样，黑 = 被挡住，彩色 = 映出了别的物体） |
| sRGB Colors and Color Maps | 开：把颜色参数和颜色贴图当作 sRGB，内部转成线性再算光照（8 位贴图应保持开启）。关：当作线性 |
| Normal Map Convention | 法线贴图约定，对所有材质生效：OpenGL（Y+，Blender、Tripo 默认）或 DirectX（Y−，虚幻引擎、Substance 默认）。用错了凸起会看成凹陷 |
| Scene Unit | 场景里 1 个单位等于多少（0.8.3）：Meters（默认）/ Centimeters / Millimeters / Inches / Feet / Custom。模型是按厘米、英寸建的（从 Maya、3ds Max、C4D、CAD 导入的常见），选对应的单位，下面各页里写着“米”的参数就按真实尺寸生效，不用再一个个改。见下方说明 |
| Unit Size (m) | Scene Unit = Custom 时：1 个单位等于多少米 |
| Anti-Aliasing | TAA（默认）：时间性抗锯齿，每帧把相机错开不到一个像素，再和前几帧混合，边缘和细小高光不再闪烁。None：关闭，边缘有锯齿 |
| TAA Current Frame Weight | 每帧新画面占的比例，默认 0.1。调小更平滑但运动时更"拖"，调大反应更快但会轻微闪烁 |

TAA 的副作用：镜头切换（相机瞬间跳到别处）后约 4 帧画面略软，属于正常现象；Debug View 看到的中间结果是没有抗锯齿的。

**Scene Unit（场景比例，0.8.3）**：BTDR 的效果按真实世界的尺寸设计，比如 AO 半径 0.6 m、皮肤散射 1 cm、雾按每米的浓度算。以前默认“1 个单位 = 1 米”，模型按厘米建（一个人 170 个单位高）时，AO、反射、雾、次表面散射全都会差 100 倍，只能逐项去调。现在只要把 Scene Unit 设成实际的单位：
- 写着“（米）”的参数按米理解，内部自动换算成场景单位：AO / Bounce Radius、Max Ray Distance、Object Thickness、Height-Field AO Radius、雾的 Density / Height Falloff / Base Height / Max Distance、散射半径和薄片厚度、吸收距离。
- 着色器内部按米写的常数（阴影偏移、光线起点的偏移、软阴影的范围、雾的噪声大小、光追探针的边距等）也一起换算。
- 写着“（场景单位）”的参数不变：Shadow Center / Range、Focus Distance，以及第 2、3 个输出口里的距离。景深的焦距、传感器宽度按毫米，不受影响。
- 实测：同一场景按厘米建（所有尺寸 × 100）并选 Centimeters，画面和按米建的平均只差 0.13%。Meters 下和 0.8.2 完全一样。

### Light 页

| 参数 | 作用 |
|---|---|
| Main Light | 只读，显示当前用的是哪盏灯 |
| Intensity Multiplier | 在灯光 Dimmer 基础上再乘的倍数 |
| Energy Compensation | 默认开（0.8.4）：粗糙金属的能量补偿。普通的 GGX 高光只算光在表面反射一次，粗糙度高时，在微观凹凸之间来回反射的那部分光丢了，粗糙金属会偏暗（粗糙度 0.8 时最多丢掉约四成）。开着时把这部分补回来，粗糙金属更亮、颜色更饱和；光滑表面和非金属几乎不变。关掉 = 0.8.3 的效果 |
| Local Lights | （0.9.0）点光、聚光和第二盏以后的平行光（局部灯）开关，默认开 |
| Light Count | 只读：例如 `1 main, 2 point, 1 cone, 0 distant` |
| Local Intensity | 所有局部灯的亮度倍数 |
| Local Falloff | 局部灯的衰减。**Light COMP Attenuation**（默认）：按灯自己的 Attenuated / Attenuation Start / End / Exp，Attenuated 关时不衰减（和 TD 的灯一样）。**Physical**：平方反比，在 1 米处达到 Dimmer 的亮度 |
| Max Shadowed Spot Lights | （0.9.1）最多几盏聚光灯有阴影，默认 2，最多 4，0 = 局部灯都不投影。按 Lights 匹配的顺序取前几盏聚光（cone）。每盏多画一张阴影图（约 +0.3 ms，阴影图只在灯或物体变化时重画，和主光一样跟 Shadow Update 走） |
| Spot Shadow Resolution | （0.9.1）聚光阴影图的分辨率，默认 1024 |
| Shadows | 阴影开关 |
| Shadow Softness | 半影宽度的倍数。0 接近硬阴影 |
| Auto Fit Shadow Range | 开：刷新场景时按几何体包围盒自动设置下面两项（地面不参与计算；0.8.5 起墙、天花板这类薄板参与计算，室内场景的阳光不会再从天花板漏进来） |
| Shadow Center / Shadow Range | 阴影覆盖范围的中心和宽度（场景单位）。范围越小阴影越清晰 |
| Shadow Resolution | 阴影图分辨率。Quality = Custom 时可改 |
| Shadow Update | On Change（默认）：只有灯光、物体的位置或形状变化时才重画阴影图，静止的场景省掉阴影的全部开销（相机怎么动都不影响）。Every Frame：每帧都重画；如果发现阴影没跟上变化，改成这个 |
| Half Resolution While Moving | 默认开。灯光或物体在动时阴影图用一半分辨率，停下后自动用全分辨率重画一次。运动中影子边缘稍软，一般看不出来 |
| Update Every N Frames While Moving | 默认 1（每帧）。设成 2–4 时，运动中每 N 帧才更新一次阴影，更省，但光源动得快时阴影会有轻微的跳动 |

地面这类只接收阴影的扁平物体（比其他物体都低、几乎没有高度）会自动不参与画阴影图，省掉一次绘制。

灯光的方向、颜色、强度直接读 Light COMP。**主光**是 Lights 匹配到的第一盏平行光（distant）：方向取它的朝向，位置不影响结果，它有软阴影、雾里的光束、次表面透射和探针 GI。

**局部灯（0.9.0）**：其余的 Light COMP——点光（point）、聚光（cone）、第二盏以后的平行光——最多 8 盏，读颜色、Dimmer、位置和朝向（每帧更新，移动灯不用刷新），聚光读 Cone Angle / Cone Delta / Cone Roll。0.9.1 起：前几盏聚光有阴影（Max Shadowed Spot Lights，3×3 PCF 软边，比主光的阴影硬一些）；所有局部灯都会照亮体积雾（灯周围的光晕、聚光的光锥），也进探针 GI 和光追反射（命中点用光追阴影射线判断遮挡）。点光、多出来的平行光还没有阴影；次表面透射只算主光。只匹配到点光、聚光时就没有主光（以前会把点光当平行光用）。

**亮度约定（和原生不同，有意为之）**：BTDR 把灯的 Dimmer × π 当作照度，颜色参数和颜色贴图按 sRGB 解码（Render 页 sRGB Colors and Color Maps）。所以同一盏灯、同一个材质，BTDR 比原生 Render TOP 亮（中灰约 1.4 倍，浅色更多），画面更接近 UE5 的默认观感。想和原生亮度接近，把 Intensity Multiplier 调到 0.3–0.5 左右，或关掉 sRGB Colors。
`Lights` 没匹配到任何灯时用内置的一盏主光，节点上会有提示。

### Environment 页

**最简单（0.7.4）**：和原生 Render TOP 一样，在网络里放一个 **Environment Light COMP**、给它的 Environment Light Map 指定全景图，BTDR 会自动使用（Source 默认是 Auto；它的 Dimmer 和 Rotate Y 也生效，用到的是哪一盏显示在 Environment Light 一栏）。

手动指定的步骤：用 Movie File In TOP 读入 `.hdr` / `.exr` 全景图 → Source 选 HDRI Map → 把这个 TOP 拖到 HDRI Map → 想看到环境就把 Background 改成 Environment。
带太阳的户外 HDRI：让 Light COMP 的方向和图里的太阳一致，影子才对得上——可以转灯，也可以用 Rotate 转 HDRI（见 §7）。觉得影子太浅就降低 Intensity 或提高灯的 Dimmer。
发布包的 `hdri/` 里放了一张晴天全景 `kloofendal_43d_clear_2k.hdr`（Poly Haven，CC0，可随意使用），可以拿来试。

| 参数 | 作用 |
|---|---|
| Source | Auto（默认）：Lights 匹配到带贴图的 Environment Light COMP 时用它的贴图，否则用 Studio。Studio：内置的程序化摄影棚（渐变 + 4 个柔光箱）。HDRI Map：用你指定的全景图 |
| Environment Light | 只读：Auto 模式下正在使用的 Environment Light COMP |
| HDRI Map | 一个等距柱状投影（equirectangular，2:1）的全景 TOP，建议 32 位浮点的 HDR 图。图里很亮的太阳只会产生高光和环境光，不会投射阴影；阴影只来自 Lights 里的那盏灯 |
| Intensity | 环境光强度 |
| Rotate | 绕竖直轴旋转环境（度） |
| Background | Color：纯色背景。Environment：直接显示环境。Transparent (alpha)：背景透明（0.7.5），第 1 个输出带透明通道（预乘，和原生 Render TOP 一样），可以直接用 Over / Composite TOP 叠到别的画面上 |
| Background Color / Blur / Intensity | 背景颜色、环境背景的模糊程度、背景亮度 |
| Distance Fade Start / End | 离相机这段距离内，物体逐渐淡入背景；用来隐藏无限地面的边缘。End ≤ Start 时关闭 |

### Indirect 页（间接光）

光线在物体之间的二次传递。都是"屏幕空间"算法：只用当前画面里看得到的东西计算，所以很快，但画面外和被挡住的东西不参与。默认全开。

| 参数 | 作用 |
|---|---|
| Screen-Space AO | 环境遮蔽（Ambient Occlusion）：缝隙、角落、物体和地面接触处，天空和环境光照不进去的地方变暗。只压暗环境光，不影响太阳直射 |
| AO Intensity | 遮蔽强度，1 = 物理正确，最大 2 |
| Bounce Light (SSGI) | 反弹光（屏幕空间全局光照）：物体被照亮后把光反射到旁边的物体上，比如红木底座把地面映成暖色 |
| Bounce Intensity | 反弹光强度 |
| AO / Bounce Radius | 遮蔽和反弹光的作用范围（米，按 Scene Unit 换算）。默认 0.6，物体越大可以设得越大 |
| Screen-Space Reflections | 屏幕空间反射：光滑表面映出画面里的其他物体（地面倒影）。没找到反射物的地方仍然显示环境反射 |
| Reflection Intensity | 反射强度 |
| Max Ray Distance | 反射光线最远找多远（米） |
| Max Roughness | 比这更粗糙的表面不做屏幕空间反射（太粗糙的反射本来就看不出物体），默认 0.6 |
| Object Thickness | 判断"光线是否打到物体"时假设的物体厚度（米）。反射里物体出现断裂就调大，出现不该有的拉丝就调小 |
| Height-Field AO | 地面接触遮蔽（默认关）：从正上方看场景，算出地面上每个点头顶和四周被物体挡住了多少天空，压暗那里的天光和天空反射。车底、桌子底下的地面会正确地变暗，物体"坐"在地上，背光、低机位时尤其明显。不受屏幕空间限制，相机从什么角度看都一样。只作用在地面这类"接收者"（朝上、且不是物体自己顶面的表面），物体本身不受影响 |
| Height-Field AO Intensity | 强度，1 = 完全按计算结果 |
| Height-Field AO Radius | 往外找遮挡物的距离（米），默认 2。物体越大设得越大 |

屏幕空间的固有限制：
- 反射只能映出画面里看得到的东西：物体的背面、画面外的物体映不出来，反射在画面边缘会逐渐淡出；朝着相机方向的反射（比如正对镜头的金属牌）也会淡出，改用环境反射。
- AO 和反弹光只考虑附近一个半径内、看得到的表面；物体被挡住的部分不参与。
- 这些效果每帧只算一个随机样本，再和前几帧混合，相机快速移动时可能看到轻微的噪点或拖影，停下来几帧后就干净了。
- Quality = Low 时 AO / 反弹光 / 反射用半分辨率计算，物体边缘会略软。

Height-Field AO 的范围和阴影一样（Light 页的 Shadow Center / Range），也和阴影图一起缓存：物体不动就不重算。它把每个物体看成"从顶面一直实心到地面"的一块，所以车底那 15 cm 的缝透进来的天光会被忽略（偏暗一点）；拱桥底下这类多层悬空的结构只按最上面一层算。为什么车底在太阳阴影里却会显得亮：亮的不是太阳光，而是天光和光滑地面反射出的天空——屏幕空间反射看不到朝下的车底盘，只能退回反射天空；这个选项就是把这部分挡掉（老赛车游戏用车底的接地阴影贴片做同样的事）。开销实测约 0.27 ms GPU（High，1080p，超跑测试场景；Low 档方向数减半）；顶视图只在物体变化时重画，一次约 0.04 ms。

### Ray Tracing 页（硬件光追）

简化版 Lumen：在节点内部把场景减面成一份"光追代理"（低模），用显卡的硬件光追对它发射光线。和屏幕空间效果的区别是光线能打到画面外和被挡住的东西：车底盘、物体背面、画面外的墙都能挡光、能被映出来。默认开启。

| 参数 | 作用 |
|---|---|
| Hardware Ray Tracing | 总开关 |
| Ray Tracing Available | 只读。显卡不支持光线查询、或光追节点出错时自动变成关，节点上会出现提示，其余功能不受影响 |
| Probe GI | 探针全局光照：在物体周围摆一个三维网格的光照探针（约 2000 个，High 按场景的长宽高比例分配，例如又宽又浅的场景 40×9×7；Low 每个方向少四分之一），每个探针向四周发 64 / 32 条光线，记下各方向来的光。物体表面的环境漫反射改用探针的结果，所以车底、桌下、墙角这类天光照不到的地方会变暗，被太阳照亮的物体会把颜色"染"到旁边（颜色渗透，color bleeding）。场景和灯不动时只算一次，不占每帧开销 |
| GI Intensity | 探针光照的强度 |
| Ray-Traced Reflections | 光追反射：每 4 个像素（Low：6 个）发一条反射光线，算出"实际看到的"和"环境贴图"的亮度比，乘到环境反射上。光滑地面里不会再映出被车挡住的天空，画面外的物体也能映出来。屏幕空间反射（SSR）找得到的地方仍然叠在最上面（它更清晰）。0.8.4 起放大到全分辨率时只混合同一个表面上的结果（按法线和深度判断），物体边缘不再出现 4×4 像素的方块 |
| Reflection Intensity | 光追反射的混合程度，0 = 只用环境反射 |
| Reflection Max Roughness | 比这更粗糙的表面不发反射光线 |
| Proxy Detail (%) | 光追代理保留原模型多少面（默认 15%）。越高越准，但每帧重建加速结构更慢；面数显示在下面的 Proxy |
| Proxy | 只读：代理的三角形数量 |

光追的几个限制（简化版 Lumen 的取舍）：
- 光线打到的表面只按"漫反射"着色，颜色是材质贴图的平均色：反射里的物体没有自己的高光和贴图细节，比真实的略暗、略平。离得近、看得清的反射仍由屏幕空间反射负责。
- 代理是减面后的模型，和真实表面有几毫米到几厘米的差别：光线从表面稍微离开一点再出发，所以紧贴的接触处由屏幕空间效果补。
- 探针间距几十厘米：比这更小的缝（比如车底 15 cm 的空隙）分辨不出，Height-Field AO（Indirect 页）可以一起开着补充。
- 实例化（Instancing）的几何体暂时不进光追代理（节点上有提示）。
- 改了材质颜色要点 Refresh Scene 才会更新代理的颜色；移动物体、灯光会自动跟上。

### Fog 页（体积雾）

真正的三维雾：灯光被物体挡住的地方，雾里会留下影子（体积光、光束，英文 light shafts / god rays）；朝着灯光方向看，雾会更亮（前向散射）。默认关闭。

| 参数 | 作用 |
|---|---|
| Volumetric Fog | 开关 |
| Density | 雾的浓度（地面高度处每米的消光系数）。0.03 是淡淡的空气感，0.2 以上是浓雾 |
| Height Falloff | 越往高处雾越淡的速度，0 = 上下一样浓 |
| Base Height | 从哪个高度开始变淡（米） |
| Anisotropy (Forward Scattering) | 各向异性：0 = 各方向一样亮；越接近 1，逆光看越亮、顺光看越暗（大气、晨雾一般 0.6–0.8） |
| Ambient Light | 环境光照亮雾的程度（来自 Environment 页的环境）。调低后被挡住的地方更暗，光束更明显 |
| Noise | 浓度的起伏，让雾不那么均匀 |
| Max Distance | 体积雾计算到多远（米），超过这个距离按这个距离的雾量算。场景越小设得越小，精度越高 |
| Fog Color (Albedo) | 雾的颜色（反照率） |
| Fog Resolution | 雾的格子数（0.7.2）：Auto 跟随 Quality（High 160×90×64，Low 128×72×48）；也可以单独选 Low / Medium / High 240×135×96 / Ultra 320×180×128。格子越多光束越细、颗粒越小，GPU 开销大致和格子数成正比（High 约 +0.3 ms） |
| Fog Current Frame Weight | 时间累积里每帧新结果占的比例（0.7.2），默认 0.1。调小（0.03–0.05）画面更稳、颗粒和闪烁更少，代价是灯光、物体移动时光束跟得更慢（拖影） |
| Fog Jitter | 每帧在格子内随机取样的幅度（0.7.2），默认 1。调小颗粒更少，但光束边缘会出现台阶感。0.7.3 起只影响画面方向，深度方向始终取满整格：只取半格时，百叶这类比格子还薄的光片会和格子“打架”，出现不顺着光的斜带（摩尔纹） |
| Fog Shadow Blur | 雾里光束边缘的软硬（0.7.3），默认 1 = 和地面、墙上的阴影一样软：离遮挡物越远越软（接触硬化软阴影，跟 Shadow Softness 走）。调大更柔、噪点更少；0 = 硬边单点（最锐利也最噪）。注意 0.7.2 里这个参数的意思是“模糊几个像素”，旧工程里调到 2–3 的，升级后建议改回 1 |
| Multiple Scattering | （0.9.1）多次散射，默认 0.5。浓雾里光在雾滴之间来回散射，整体更亮、更“白”，光束周围也有一圈柔光；0 = 只算一次散射（0.9.0 的效果）。用倍频近似（Wrenninge 2013），几乎不增加开销 |

**光束是"雾里的影子"**：被照亮的雾和被挡住的雾挨在一起才看得出一道一道的光。想要明显的光束：
- 要有大的遮挡物和缝隙：窗户、百叶、柱廊、树冠。几十厘米的小物体只能在大片亮雾里留下很细的暗影，基本看不出来。
- 相机站在阴影里、朝着灯光方向看（逆光）；Anisotropy 0.7 以上，Ambient Light 调低（0.1 左右），Density 0.1–0.3。

雾按 160×90×64（Low：128×72×48）个格子计算，光束的边缘比较柔和，细小的物体留不下清晰的影子。
雾的结果会和前几帧混合来去掉噪点（时间累积），所以改灯光、雾的参数之后约 10 帧（1/6 秒）才完全跟上，灯光快速运动时光束会有轻微拖影。

**雾有颗粒感、闪烁（抖动）时怎么调**：颗粒来自每个格子每帧只随机取一个点、再在时间上平均（蒙特卡洛噪声）；遮挡物越细（百叶、铁丝网）、雾越浓，噪声越明显。按效果从大到小：Fog Shadow Blur 保持 1 或调到 1.5；Fog Resolution 选 High；Fog Current Frame Weight 调到 0.04 左右；Fog Jitter 调到 0.5。百叶窗示例场景用的是 High / 0.04 / 0.5 / Blur 1（GPU 约 +0.4 ms）。另外，用脚本驱动参数时不要每帧给参数重复赋同一个值：TD 会把它当成"变了"，阴影图和雾的历史每帧被重置，画面会满是块状噪点。

**百叶后面的雾里有一道道斜条纹**：那是相邻叶片之间的“光片”——每两片叶片之间漏进来的一层平面光，从斜角看就是平行的斜条带，方向由叶片走向和太阳方向共同决定，真实世界也会这样。0.7.2 及以前，雾里的阴影没有软化，光片几米外仍是硬边，所以条纹又多又锐；0.7.3 起和地面阴影一样随距离变软，远处的条纹会自然融成一整束光。想要更柔：调大 Fog Shadow Blur 或 Light 页的 Shadow Softness；想让光片和光束方向一致：让太阳正对窗户（灯的 Y 旋转接近窗户朝向）。如果看到的斜带**不顺着光的方向**（比如横穿光束、铺在地面上方），那是格子采样的摩尔纹，0.7.3 已修；Max Distance 别设得比场景大太多（房间里 10–20 就够），格子越薄越不容易出现。

### Transparency 页（透明与折射，0.6.0；光追折射 0.7.0）

玻璃、水、宝石这类**折射类**透明物体。做法和 UE5 的"前景透明层"、Unity HDRP 的屏幕空间折射同一路线：透明物体单独渲染一层，再测出它的厚度，最后算折射、吸收和反射。场景里没有透明物体时这一页不占任何性能。

**最简单的用法：把物体拖进槽里**
1. 在 Transparency 页的 **Refractive** 列表点 **+**（默认已有 1 个空槽）。
2. 把玻璃物体的 **Geometry COMP 拖进槽的 Geometry 框**，或者手写路径，可以用通配符，例如 `glass_*`。
3. 选一个 **Preset**，完成。

拖进槽里的物体即使不在 Render 页 Geometry 参数的匹配范围里，也会被加入渲染。

**不设置也能用**：没放进槽的物体，如果它的 PBR MAT 的 Alpha 页 **Alpha Front 小于 1**、或挂了 **Alpha Map**，自动按玻璃（Default IOR）渲染。PBR MAT 的 Common 页打开 **Alpha Test** 时按镂空处理（树叶、铁丝网），不当透明。

| 参数 | 作用 |
|---|---|
| Transparency | 总开关。关闭时所有物体按不透明画 |
| Transparent Objects | 只读：当前按折射类渲染的物体数 |
| Default IOR | 自动识别出来的透明物体用的折射率 |
| Absorption Distance | 自动识别出来的物体的吸收距离（见下） |
| Alpha Test Mode | （0.8.4）PBR MAT 打开 Alpha Test（镂空）时怎么切。**Threshold**（默认，和原生一样）：Alpha 小于 Alpha Threshold 的地方整片切掉。**Hashed**（哈希镂空）：按 Alpha 值随机保留对应比例的像素，例如 Alpha 0.3 留 30%，远处的细草叶、铁丝网不会整片消失；配合 TAA 平均后看起来是半透明。代价：近看能看到细小的噪点 |
| Refraction Method | 怎么找到玻璃后面的东西（见下）。**Screen Space**（默认）：屏幕空间，最快最清晰，但只能看到画面里有的东西。**Hybrid**：屏幕空间找得到的地方用屏幕空间，找不到的地方（画面外、玻璃后面的玻璃）用光追补。**Ray Traced**：全部用光追 |
| Refractive（列表） | 透明槽，每条一组物体 |
| · Geometry | 拖入 Geometry COMP，或写路径 / 通配符 |
| · Preset | Glass、Frosted Glass（磨砂）、Tinted Glass（茶色）、Water、Ice、Crystal、Diamond、Acrylic、Window (thin)（薄窗玻璃）、Custom。选了以后自动填下面几项 |
| · IOR | 折射率：玻璃 1.5、水 1.333、冰 1.31、钻石 2.42。越大，透过去的画面弯得越厉害 |
| · Roughness Override | -1 = 用材质的粗糙度；大于等于 0 时覆盖，磨砂玻璃一般 0.2–0.5 |
| · Thin Walled | 薄壁：窗玻璃、肥皂泡、单面的平面、薄膜。不偏移、不按厚度吸收；有粗糙度时是“磨砂薄膜”：贴着它的东西清楚，离得越远越模糊（0.8.1） |
| · Thin Transmission Lift | 只对薄壁有效（0.8.1）：透过薄膜看到的颜色往白色提亮多少。0 = 按 Base Color 染色（以前的效果）；薄膜、纸、皮肤这类很薄的东西透过来的光比表面颜色浅，一般 0.3–0.6 |
| · Absorption Distance | 吸收距离（米）：光在物体里走这么远后，颜色正好是材质的 Base Color。越小颜色越浓；越厚的地方越深 |
| · Cast Shadow | None（默认，玻璃不挡光）/ Opaque（按不透明物体投影） |
| · In Ray Tracing | 是否进入光追代理（默认关：光直接穿过玻璃） |
| · Refraction Scale | （0.8.4）折射弯曲的倍数。1 = 物理正确（默认）；0 = 完全不弯，直接看穿；大于 1 弯得比真实的更厉害（构图需要放大效果、又不想把 IOR 调到不真实时用）。屏幕空间和光追折射都生效 |
| · Absorption Color Source / Absorption Color | （0.8.4）吸收颜色从哪来。**Base Color**（默认，和以前一样）：内部颜色就是材质的 Base Color。**Custom**：用这里的 Absorption Color，表面颜色仍然是 Base Color。例如粉色的表面涂层包着无色的介质：Base Color 设粉色，Absorption Color 设白色 |

材质参数怎么用：
- **Base Color**：透明体内部的颜色（槽的 Absorption Color Source = Custom 时，内部颜色改用槽里的 Absorption Color）。清玻璃用接近白色，有色玻璃、水用浅色，配合 Absorption Distance 控制浓淡。
- **Alpha Front**：0 = 完全透明；中间值 = 表面带一层雾面的漫反射涂层（有色塑料、脏玻璃）。
- **Roughness**：同时控制反射和透射的模糊，磨砂玻璃就是调它（或用槽的 Roughness Override）。
- **Normal Map**：扰动折射，水面波纹、压花玻璃都靠它。
- **Metallic** 在透明物体上不起作用。

**光追折射（Refraction Method = Hybrid / Ray Traced，0.7.0）**：需要 Ray Tracing 页的硬件光追开着并且可用。光线真的在玻璃里走：从正面折射进去，在背面折射出来，遇到全内反射就在里面反弹，最多穿过 8 个面，所以能看到玻璃后面的玻璃、画面外的物体，颜色按每一段在玻璃里走的距离变深。代价和取舍：
- 光追用的是减面后的"光追代理"（Ray Tracing 页的 Proxy Detail），球这类曲面的折射会带一点棱角；打到的物体按"漫反射 + 平均色"着色，没有贴图细节和高光，所以比屏幕空间的软一些、平一些。近处清楚的折射，Hybrid 会优先用屏幕空间。
- 1/4 分辨率（Low：1/6）计算，再在时间上平均：相机快速移动时磨砂玻璃上能看到一点噪点。
- 改了槽的 IOR / 吸收距离 / 薄壁，光追部分会自动刷新一次场景。
- 开销（RTX 5080 Laptop，1080p，测试场景）：GPU 约 +0.1 ms，CPU 约 +0.25 ms。Screen Space 时为 0。

限制（这一版的取舍）：
- 屏幕空间（默认）只处理最前面一层透明表面：玻璃后面的另一块玻璃看不见，要看到用 Hybrid / Ray Traced。互相穿插、嵌套的透明物体（杯子里的水）在屏幕空间下会算错。
- 屏幕空间折射只能"看到"画面里有的东西，看到画面外时改用环境贴图（Hybrid 用光追补）。
- 玻璃不投彩色阴影，没有焦散和色散。
- 烟雾、粒子这类"不折射的透明"（混合透明）暂时不支持：开了 Blending 又挂了 Alpha 贴图的材质按折射类画，节点上会提示。

性能（RTX 5080 Laptop，1080p，测试场景里透明物体占画面约三分之一）：GPU 约 +0.6 ms，CPU 约 +0.85 ms（两个额外的 Render TOP）。没有透明物体时为 0。

### Subsurface 页（次表面散射，0.8.0）

**次表面散射**（Subsurface Scattering，SSS）：光钻进半透明材质内部、散开后从附近别的位置射出来。皮肤边缘透红，玉、蜡、大理石、牛奶看起来"软"，耳朵、树叶、灯罩背光时透亮，都是它。做法和 UE5 一样分两部分：
- **散射**（对应 UE5 的 Subsurface Profile）：只把漫反射光照在屏幕上按一条散射曲线模糊开，高光和反射保持清晰。
- **透射**（对应 UE5 的 Subsurface / Two Sided Foliage）：背光时光从物体背面透过来。厚度直接从太阳的阴影图量出来，不需要厚度贴图。

场景里没有 SSS 物体时这一页不占任何性能（相关节点全部旁路）。

**用法：和透明槽一样，把物体拖进槽里**
1. 在 Subsurface 页的 **Subsurface** 列表点 **+**（默认已有 1 个空槽）。
2. 把模型的 **Geometry COMP 拖进槽的 Geometry 框**，或者写路径 / 通配符，例如 `skin_*`。
3. 选一个 **Preset**，完成。颜色、粗糙度、法线贴图仍然读 PBR MAT。

| 参数 | 作用 |
|---|---|
| Subsurface | 总开关 |
| Subsurface Objects | 只读：当前按 SSS 渲染的物体数 |
| Subsurface Quality | Auto（跟随 Render 页的 Quality）/ High（每个方向 15 个采样）/ Low（9 个） |
| Scatter Scale | 所有槽的散射半径一起乘这个数。模型的单位不是米时，先设 Render 页的 **Scene Unit**（0.8.3）；这里只用来整体加强或减弱散射（0.8.2 及以前要用它校正比例，比如 10 个单位高的人头设成约 30） |
| Transmission | 透射总开关 |
| Subsurface（列表） | SSS 槽，最多 8 条，每条一个“散射档案”，可以管一批物体 |
| · Geometry | 拖入 Geometry COMP，或写路径 / 通配符 |
| · Preset | Skin（皮肤）、Jade（玉）、Wax（蜡）、Marble（大理石）、Milk（牛奶 / 奶油）、Soap（肥皂）、Leaf (thin)（树叶）、Paper (thin)（纸、灯罩）、Custom。选了以后自动填颜色、半径、薄片设置 |
| · Scatter Color | 散射颜色：哪个通道的值大，那个颜色的光在材质里走得远。皮肤红光走得最远，所以阴影边缘发红 |
| · Scatter Radius (m) | 光在材质里横向扩散的距离（米）。皮肤约 1 cm、玉约 2 cm。越大越“软”，细节越糊 |
| · Strength | 0 = 不散射，1 = 完全按档案散射 |
| · Texture Detail | 贴图细节保留多少：0 = 贴图一起被糊开，1 = 贴图完全清晰（颜色会偏平），默认 0.5 |
| · Transmission Color | 背光透过来的光的颜色（再乘材质的 Base Color）。黑色 = 不透光 |
| · Transmission Strength | 透射强度 |
| · Thin (sheet) | 薄片模式：树叶、纸、灯罩。不做散射模糊，只算透射，厚度用下面的值，背面的环境光也会透过来 |
| · Sheet Thickness (m) | 薄片的厚度，只在 Thin 打开时用 |

调法：
- 物体看起来像蜡、细节糊了：减小 Scatter Radius，或把 Texture Detail 调大。
- 背光时不透光：确认 Light 页的阴影是开着的（透射靠阴影图量厚度），厚的部分本来就不透光，只有耳朵、手指、薄边、镂空雕刻这类几厘米以内的地方会亮。
- 透光太亮：减小 Transmission Strength。
- 同一个物体既在透明槽又在 SSS 槽里时按透明画，Status 会提示；Constant MAT 不受光，不做 SSS。

**Debug View** 新增三项：Subsurface Profile（按槽上色，灰色 = 不是 SSS 物体）、Subsurface Irradiance（左半边模糊前、右半边模糊后的光照）、Subsurface Transmission（只看透射）。

限制：
- 屏幕空间方法只能散射画面里看得到的光：物体背面、画面外的光散不过来；镜头贴得很近时散射范围被限制在 64 像素，会显得偏硬。
- 透射只来自那一盏平行光。阴影图分不清“自己的背面”和“别的遮挡物”：被别的物体挡住时透射也会变弱（一般是对的）。
- 反射（SSR、光追）里看到的 SSS 物体是散射过的上一帧画面；光追代理里只有平均色，不散射。
- 切换 Subsurface 开关的头几秒，阴影和时间累积会重新收敛一次。

性能（RTX 5080 Laptop，1080p，SSS 物体占画面 1/4 到 1/3）：GPU 约 +0.15 ms（`sss_h`、`sss_v` 各约 0.05–0.07 ms，composite 多写一张缓冲约 0.04 ms），CPU 约 +0.1 ms（两个 GLSL TOP）。没有 SSS 物体时为 0。

### Post 页（镜头效果）

都在 HDR 画面上计算，顺序是 体积雾 → 抗锯齿 → 景深 → 运动模糊 → Bloom / 自动曝光 → 调色。除 Bloom 外默认都关，关闭的效果不占性能。

| 参数 | 作用 |
|---|---|
| Bloom Intensity | 泛光（Bloom）强度：很亮的地方向周围散出光晕。默认 0.05（很轻），0 关闭，0.3 左右明显 |
| Bloom Threshold / Knee | 多亮才开始发光。阈值按曝光之后的亮度算：1 = 屏幕上刚好变白的亮度；Knee 越大过渡越柔 |
| Bloom Radius | 光晕散多远（0–0.95，默认 0.65）。只改变光晕大小，不改变总亮度；小 = 紧贴亮处，大 = 像镜头那样大范围的柔光。Quality = Low 时少算最大的两级，光晕的最大范围约为 High 的 1/4 |
| Auto Exposure | 自动曝光（眼睛适应）：按画面平均亮度自动调亮或调暗，从暗处转向亮处时有逐渐适应的过程。Grade 页的 Exposure 在它之上再做补偿 |
| Min / Max Luminance (EV) | 自动曝光的工作范围：画面比 Min 还暗时不再继续提亮，比 Max 还亮时不再继续压暗 |
| Target Grey | 把画面平均亮度调到多少，默认 0.18（中灰）。整体偏暗就调大 |
| Adapt Speed To Brighter / Darker | 适应速度，数值越大越快。默认变亮快（3）、变暗慢（1），和人眼一样 |
| Depth of Field | 景深：对焦距离以外的物体变虚 |
| Focus Distance | 对焦距离（场景单位），沿相机朝向量 |
| F-Stop | 光圈值。越小越虚（f/1.4 很虚，f/8 几乎全清楚） |
| Focal Length (mm) | 焦距。0 = 按相机的视角和下面的传感器宽度自动算（推荐） |
| Sensor Width (mm) | 传感器宽度，默认 36（全画幅）。和焦距一起决定虚化程度 |
| Max Blur Radius (px) | 虚化半径的上限 |
| Motion Blur | 运动模糊：相机移动、转动时画面沿运动方向拖影 |
| Shutter | 快门时间，占一帧的比例。0.5 相当于电影常用的 180° 快门；1 拖影最长 |
| Max Blur Length (px) | 拖影长度上限 |

运动模糊目前只来自相机运动：相机不动、物体自己在动时物体不会糊（需要逐物体的运动矢量，后续版本加）。
景深和运动模糊的采样数跟随 Quality：Low 档采样少一半。

### Grade 页

| 参数 | 作用 |
|---|---|
| Exposure (EV) | 曝光补偿，每 +1 亮一倍。开了自动曝光时在自动结果之上再补偿 |
| Tone Mapping | ACES 或 None |
| Vignette | 暗角强度，默认 0（0.7.5 前默认 0.3） |
| Grain | 胶片颗粒强度，默认 0（0.7.5 前默认 0.01） |

## 3b. 性能

RTX 5080 Laptop 上实测（1080p，测试场景：两件带 4K 贴图的模型，60 万三角形，相机在环绕，灯光和物体静止）：

| | GPU | CPU |
|---|---|---|
| **BTDR High，默认设置** | **约 2.1 ms** | 约 1.3 ms |
| BTDR Low，默认设置 | 约 1.0 ms | 约 1.3 ms |
| BTDR High，1440p / 4K | 约 3.8 / 8.9 ms | 同上 |
| 同一场景用 TD 原生 Render TOP（没有任何后期和间接光） | 约 0.7 ms | 约 0.5 ms |

其他显卡没有实测，按显卡跑分粗略换算（1080p，默认设置，偏保守）：

| 显卡 | High | Low |
|---|---|---|
| RTX 4060 Laptop | 约 5 ms | 约 2.6 ms |
| RTX 2060（台式） | 约 5.5 ms | 约 2.9 ms |
| RTX 2060（笔记本） | 约 7 ms | 约 3.5 ms |

省性能的办法，按效果从大到小：
- **Quality = Low**：GPU 约减半。
- 4K 输出：屏幕空间效果按像素算，用 Low，或关掉 Indirect 页的 Bounce Light。
- 场景里的 Light COMP 如果开着原生阴影（Shadow Type 不是 Off），TD 每帧会给它画一张 BTDR 用不到的阴影图（测试场景里约 0.4 ms CPU、1.4 ms GPU）。只用 BTDR 出图时把灯的 Shadow Type 设成 Off，BTDR 自己的阴影不受影响。这种情况 Status 会给出提示。
- CPU 紧张时关掉 Ray Tracing 页的 Ray-Traced Reflections（约省 0.35 ms CPU），只留 Probe GI：场景和灯不动时探针不重算，几乎没有开销。
- 灯光或物体一直在动时阴影图每帧重画（GPU 多约 0.1–0.2 ms、CPU 多约 0.3 ms），可以把 Light 页的 Update Every N Frames While Moving 设成 2–4。
- 没人查看或使用输出时节点不计算，不占性能。

## 4. 输出

| 输出口 | 内容 |
|---|---|
| 第 1 个 | 最终画面，sRGB 8 位 |
| 第 2 个 | HDR 线性画面（体积雾、抗锯齿、景深、运动模糊之后，Bloom 和调色之前），16 位浮点。alpha：到相机平面的距离（场景单位，抗锯齿后的稳定值） |
| 第 3 个 | 深度：到相机平面的距离（场景单位），32 位浮点，背景 = 相机远裁剪面 |

## 5. 材质支持

| 材质 | 读取的内容 |
|---|---|
| PBR MAT | Base Color、Metallic、Roughness、Ambient Occlusion、Emit 的数值和贴图；Normal Map 和 Bump Scale；各贴图的 Channel Source |
| Phong MAT | 只取 Diffuse 颜色和 Color Map，粗糙度固定 0.5 |
| Constant MAT | 和 TD 里一样不受光（0.7.5）：只显示颜色和 Color Map，没有明暗、阴影和反射。注意颜色仍然经过 Grade 页的色调映射，要完全原色把 Tone Mapping 设成 None |
| 没有材质 | 默认灰色，粗糙度 0.5 |
| 其他（自定义 GLSL MAT 等） | 默认灰色，节点上有警告 |

和原生 PBR MAT 一样，数值和贴图相乘：只用贴图时把对应数值设成 1。

**贴图坐标（0.8.3）**：PBR MAT 每张贴图的这些设置都会跟随，改了立即生效，不用 Refresh：
- **Extend U / V**（贴图坐标超出 0–1 时怎么办）：Repeat 重复、Hold 拉伸边缘、Mirror 镜像重复、Zero 透明。
- **Filter**（过滤方式）。各向异性过滤取材质的设置，最低 4×（斜着看的地面不会糊）。
- **SOP Texture Coord**（用第几套 UV）：uv0 和另外一套（比如给 AO 贴图、光照贴图用的 uv1）。一个材质里除了 uv0 只能再用一套，用了两套以上时按编号最大的那套读，节点上有提示。
- **Texture Sampling Mode**：Regular（按 UV）和 Screen Space（按屏幕位置贴，图案不随物体移动）。

TD 里贴图的**平铺**（Repeat 次数）和**偏移**不在材质上，要在几何体的 UV 上改：用 Texture SOP（Scale / Offset），或 Transform SOP 只变换 UV。BTDR 读的就是改过的 UV，和原生 Render TOP 结果相同（测试里两者逐像素一致）。

实例化（Instancing）时 Geometry COMP 的 Instance Color 会乘到基础色和自发光上（0.7.1），粒子可以各自有颜色和亮度。

### 警告在哪里看

- Render 页的 **Status** 显示警告条数和第一条。没有问题、但有省性能的建议时，会在 `OK: N geometry` 后面接一条 `tip`（例如主光开着原生阴影，见 §3b），不算警告，节点上也不会出现黄色三角。
- 完整列表在节点内部的 `status` DAT 里（进入 `renderBTDR`，或用 `op('renderBTDR1/status').text`）。
- 有警告时节点上会出现黄色三角标记。

常见警告：Lights 没匹配到灯（改用内置主光）、材质不是 PBR MAT、相机不是透视相机、几何体里没有开 Render 标志的节点。

## 5b. 进入组件看内部（0.8.1，0.8.2 重新排版）

`renderBTDR` 内部的每个节点都写了注释（节点 Comment），左边有一块总览面板说明整条渲染流程。0.8.2 起节点按功能分成 20 组，按一帧的数据流从左到右、从上到下排列，每组用框圈起来、标题写它做什么：脚本与控制 → 场景镜像与相机 → G-Buffer → 阴影、Height-Field AO、环境光 → SSR、SSGI、硬件光追 → 光照合成 → 次表面散射 → 透明层、折射 → 体积雾 → 抗锯齿、景深、运动模糊 → 自动曝光、Bloom → 输出 → 封面，最下面是着色器源码。只是想用 BTDR 不需要进去；想了解它怎么工作、或者排查问题时可以看。中间结果用 Render 页的 Debug View 看更方便。

## 6. 当前限制

- POP 几何体的贴图 0.8.1 起正常显示（以前只读到一个角的颜色）。
- 主光是一盏平行光，另外最多 8 盏局部灯（点光、聚光、平行光），局部灯没有阴影、不进雾和光追（0.9.1 补）。次表面散射的透射只来自主光。Ambient Light COMP 会加到环境漫反射上（0.7.5），Environment Light COMP 见 Environment 页。
- 只支持透视相机。
- 不读取：高度图和视差、Specular Level、Rim；Texture Sampling Mode 的 Triplanar（三平面投影，按 Regular 处理并在节点上提示：原生 PBR MAT 在 TD 2025.33230 里这个模式本身就不起作用，没有可对齐的效果）；POP 上自定义的 Texture Coord Attribute（只读 `Tex`）；一个材质里第三套及以后的 UV。透明见 Transparency 页一节（Alpha Test 镂空在阴影里还按不镂空投影；Hashed 镂空的噪点图案按世界坐标生成，运动的物体上图案会轻微“游动”）。
- 不支持：骨骼变形、Material SOP 逐面材质。Geometry COMP 嵌套（子级里的 Geometry COMP）0.7.5 起支持；Geometry COMP 的 Render 标志关掉就不画（和原生一样）。线条（Line SOP 等）能画，但不参与光追。
- 内部位置存成相对相机的 16 位浮点：离相机越远精度越低（5 m 处约 4 mm，50 m 处约 3 cm），几十米外的物体阴影可能出现瑕疵。阴影只覆盖 Shadow Range 以内。
- 反射、AO、反弹光是屏幕空间算法，限制见 Indirect 页一节；光追部分的限制见 Ray Tracing 页一节。
- 运动模糊和反射、反弹光的时间混合只考虑相机运动；物体自己运动时可能有轻微拖影。
- 没人查看或使用输出时节点不计算，不占性能。

## 7. 素材建议

### 法线强度

法线贴图的强度由 PBR MAT 的 **Bump Scale** 控制。从高模烘焙的法线贴图一般用 1.0。
AI 生成的模型（比如 Tripo）起伏既在模型里、又在法线贴图里，强度开到 1.0 会叠加两遍，表面看起来像融化了，用 0.2 左右。

### 法线贴图的两种约定

法线贴图分 OpenGL（Y+，绿通道朝上）和 DirectX（Y-，绿通道朝下）两种，用错了凸起会看成凹陷。
BTDR 默认按 OpenGL 约定读取，和 Blender、Tripo 等工具的默认导出一致；虚幻引擎、Substance 默认导出的是 DirectX，
用这类贴图时把 Render 页的 **Normal Map Convention** 改成 DirectX。
（这个开关对整个节点的所有材质生效；同一场景里混用两种约定时，给其中一种贴图接一个 Level TOP 把绿通道反相。）

### HDRI 和太阳方向

- 带太阳的户外 HDRI：用 Environment 页的 **Rotate** 把图里太阳的方向转到和 Light COMP 一致，金属反光里的太阳、天空的明暗和投影方向才对得上。Rotate 每加 1°，HDRI 里的太阳绕竖轴转 1°。
- **Background Blur** 0.1 左右：背景略微虚化，主体更突出；0 是清晰原图，0.25 以上接近纯渐变的影棚感。
- 免费的 HDRI 可以在 Poly Haven 下载（CC0）。
- 所有贴图默认开 4× 各向异性过滤，斜着看的表面（地面、侧面）贴图不会糊。

### 示例网络里的做法

`BTDR_Example.tox` 用的都是 TD 自带的 SOP 和原生 PBR MAT，可以直接参考：
- 灯光的原生阴影是关的（BTDR 自己画阴影，见 §3b）。
- 发光方块：PBR MAT 的 Emit 颜色调亮（超过 1），配合 Post 页 Bloom Intensity 0.15。
- 球用 Sphere SOP 的 Polygon 类型、Frequency 10：面数太少时球面会看得出棱角。

## 8. 更新到新版本

用新的 `BTDR.tox` 覆盖 Palette 里的旧文件，然后把工程里的 `renderBTDR` 删掉重新拖入。
已经在工程里的节点不会自动更新；参数要重新设置（只改过几项的话，可以先记下 Version 和改过的参数）。
当前版本号在节点的 Info 页（0.7.4 以前叫 About 页）。

## 8b. 加密发布（给作者，0.7.6）

想用 TD 的 Privacy（组件隐私密码）隐藏内部实现时，用 `BTDR_Shell.tox`，不要直接给 `BTDR.tox` 加密：加密后的组件不能把内部的 TOP 当作节点预览，节点方块上会是空的。

`BTDR_Shell.tox` 是一个两层的组件：外层 `renderBTDR` 是不加密的壳，上面有全部参数页、三个输出口和节点预览；里层 `core` 是完整的渲染器。做法：把 `BTDR_Shell.tox` 拖进网络 → 进入 `renderBTDR` → 右键 `core` 设置 Privacy 密码 → 回到上一层，右键 `renderBTDR` 另存为 tox 发布。用法和普通版完全一样；壳里只有三个 Out TOP 和一个转发按钮的小脚本，看不到着色器和代码。

## 9. 许可和素材

- BTDR 本身：PolyForm Noncommercial 1.0.0 许可（见 `LICENSE`）。**禁止商业用途**；个人学习、研究、艺术创作等非商业用途可以免费使用和修改。转发或再发布（含修改版）时必须保留 `LICENSE` 里那行 `Required Notice:`，即注明出处“BetterTDRender by Xikai Lei”和仓库地址；用它做的作品公开展示时也请注明。**商业用途需要单独授权**（商业授权），请联系作者 TD学长：微信 TD_Xuezhang、闲鱼搜“TD学长”、邮箱 max_lei_in_london@163.com 或 ginicholaslbert@gmail.com（节点的 Info 页也有）。源码：https://github.com/Maxwel-Lei/BetterTDRender
- 示例网络只用 TD 自带的几何体，没有外部素材。
- `hdri/kloofendal_43d_clear_2k.hdr`：Poly Haven（polyhaven.com），CC0。
