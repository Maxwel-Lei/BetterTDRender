# BetterTDRender（BTDR）实现参考（第 1b 份）

第 1 份 `IMPLEMENTATION.md`（§0–§9b，含维护规则和锚点约定）。本份：§9c M3 屏幕空间间接光和体积雾、§9d M4 硬件光追、§9e M6a 透明与折射。第 2 份 `IMPLEMENTATION_2.md`（§10–§13）。

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

## 9e. M6a：透明与折射（0.6.0）

设计和取舍见 `M6_TRANSPARENCY.md`。这里记录实现。

**分类（`EXT.SLOTS`、`EXT.TRANSCLASS`）**
- Transparency 页的序列参数 `Refr`：每块 8 个参数（`Refr<i>geo / preset / ior / rough / thin / absorb / shadow / inrt`）。序列最少 1 块，空的 Geometry 被忽略。
- Refresh 时先解析槽：一个物体可能被多个槽匹配，以第一个槽为准，后面的给警告。槽里的物体不在 Geometry 匹配范围内时会补进场景。
- 没进槽的物体看 PBR MAT 自动判断：Alpha Test 开 → 不透明（镂空）；`alphafront` < 1 或有 Alpha 贴图 → 折射类。开了 Blending 又有 Alpha 贴图 → 警告（混合类在 M6b）。
- Transparency 关闭时全部按不透明处理。只读参数 `Transcount` 是 Switch 的开关依据（参数表达式能跟踪依赖，storage 不行）。

**镜像和材质（`EXT.TRANSSPLIT`、`EXT.TRANSMAT`、`EXT.REFRPRESET`）**
- 折射类镜像命名为 `scene/t<i>`：`gbuffer` 的几何体模式是 `scene/g*`，自然不画它们；`tgbuffer` / `tback` 画 `scene/t*`。
- 镜像材质按（源材质、类别、槽）各建一份，因为同一个 PBR MAT 在不同槽里的 IOR 不同。
- `uTrans` / `uTrans2` 全部是表达式：槽参数（`parent.BTDR.par.Refr<i>ior` 等）或全局默认（`Defaultior`、`Absorbdist`），加上 PBR MAT 的 `alphafront`、`alphamap`、`alphatest`、`alphathreshold`。材质仍然不读每帧数据（`GBUF.SHARED`）。
- 预设由 `parexec` 在 `Refr<i>preset` 变化时调用 `ApplyPreset(i)` 写进槽参数；改 geo / shadow / inrt 或增删槽触发 Refresh。
- `EXT.TRANSSHADOW`：折射类默认不进阴影的投影物体列表（`scene/t<i>`，槽的 Cast Shadow = Opaque 时才进）；默认也不进光追代理（In Ray Tracing）。

**渲染（`BUILD.TRANS`）**
- `tgbuffer`：相机 `cam_jit`（和不透明 G-Buffer 同一个抖动），5 个 rgba16float 颜色缓冲，深度测试只在透明物体之间，所以得到最前面一层。
- `tback`：同样的几何体和材质，Cull Face = Front Faces，得到最近的背面；用 1（法线）和 2（位置）两个缓冲。
- 与不透明物体的遮挡在 `refract` 里逐像素判断（两个 Render TOP 没有共享深度）。

**`refract.frag`（`REFR.*`）**
- `REFR.LAYER`：透明表面在不透明表面前面才处理，否则原样输出。
- `REFR.THICKNESS`：厚度 = 背面视深（被不透明表面截断）− 正面视深，再除以视线和相机朝向的夹角余弦换算成沿视线的长度。没有背面（单面网格）当薄壁。
- `REFR.DIR`：
  - 薄壁：方向不变。
  - 实心：正面折射得到 T1；沿 T1 走厚度到 Pb，在 Pb 的屏幕位置重新读背面缓冲，取那里的背面位置（投影到 T1 上的距离）和法线；在背面再折射一次。
  - 掠射（cos < 0.3）或全内反射时，出射方向退回视线方向（平板的出射方向）。第一版直接用视线处的背面、并在全内反射时反射，结果顶面发黑、球边有黑环，改成这样后消失。
- `REFR.SAMPLE`：从出射点沿出射方向做 16 步指数步进（2 cm 起、每步 ×1.6，约到 20 m），对照不透明深度找交点。取不透明画面（`composite`，本身没有透明物体，所以不会采到玻璃自己）的 mip：`lod = 粗糙度² × 9 + 粗糙度 × log2(1 + 距离 × 4)`（薄壁不加距离项），就是磨砂。出屏幕或到相机后面时用 `envRadiance(T, 粗糙度)`，靠近屏幕边缘时渐变过去。
- `REFR.ABSORB`：Beer-Lambert，透射率 = Base Color^(厚度 / 吸收距离)；薄壁直接乘 Base Color。
- `REFR.SURFACE`：环境镜面（菲涅尔用 `envBRDFApprox`，F0 由 IOR 算）+ 太阳 GGX 高光（`sunShadow`，玻璃本身不在阴影图里）+ 不透明度那部分按漫反射涂层算（环境辐照度 + 太阳 / π）+ 自发光。合成：`(1 − F) × [(1 − α) × 透射 × 吸收 + α × 涂层] + 反射 + 高光 + 自发光`。
- 输出 1 / 2：合并后的位置和法线（透明层在前就用它），交给 `fog_apply`、`taa`（以及读 TAA alpha 深度的景深、运动模糊），玻璃轮廓有自己的深度。

**旁路**：`trans_src` / `tpos_src` / `tnrm_src` 的表达式 `Transparency and Transcount > 0`。为 0 时 `refract`、`tgbuffer`、`tback` 都不被拉取。实测：A/B 和 0.5.1 比（示例网络，没有透明物体）最终画面平均差 0.00000，99.9% 分位 0.00012，只有 0.004% 的像素差超过 1/255。

**还没做（M6a 剩余）**：3 个 Debug View（透明层、厚度、折射偏移）、材质库 tox、拖到节点方块上自动建槽、Quality Low 半分辨率、把 RT4 打包进 RT0.a / RT2.a（省一个 Render Select）、镂空物体在阴影里也镂空。

（§10 起见 `IMPLEMENTATION_2.md`。）
