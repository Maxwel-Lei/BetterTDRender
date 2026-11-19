# [BTDR:FILE.ANNOT] annotations.py — 给 renderBTDR 内部网络加 TD 自带的注释（0.8.1）。
# build.py 构建完后执行 annotate(C)：
#   1. 每个节点的 Comment（NOTES / 着色器 DAT 按 SHADER_NOTES 自动生成）；
#   2. 按功能分组的 Network Box（GROUPS，框里混进别组的节点时自动跳过，记进构建日志）；
#   3. 网络左侧的总览面板（OVERVIEW）。
# 只加注释，不移动、不增删任何节点和连线。文字面向会用 TD 的人：说清楚做什么、输入从哪来、受哪些参数控制、
# 对应文档里的哪个锚点（[BTDR:...]，在 docs/IMPLEMENTATION*.md 里搜）。

NOTES = {
    # ---------------- 脚本与控制 ----------------
    'BTDRExt': '扩展类（Python）：Refresh 场景镜像、解析槽位、状态、封面、Shell 同步等全部逻辑都在这里。源文件 ext/BTDRExt.py。[BTDR:FILE.EXT]',
    'parexec': '参数回调：Camera / Geometry / Lights / 槽位改动时调用 Refresh，选预设时填值，脉冲按钮。源文件 ext/parexec.py。[BTDR:FILE.PAREXEC]',
    'execute': '组件创建 / 工程打开时同步 Refresh 一次，2 帧后再补一次，5 帧后按需弹出作者信息。源文件 ext/execute.py。[BTDR:FILE.EXECUTE]',
    'scene_watch': '每 30 帧比较一次场景签名（相机、几何体、材质、灯），有变化就自动 Refresh。开销约 0.04 ms / 30 帧。[BTDR:EXT.WATCH]',
    'cover_warm': '加载封面显示期间每帧拉取渲染结果，让着色器编译、时间累积填满，封面撤下时画面已经稳定。[BTDR:EXT.COVER]',
    'uniforms': '全局 uniform 数组（4 通道 × 68 槽，uB[]）：相机、太阳、阴影、环境、各效果开关和参数，每帧算一次，所有着色器共用。[BTDR:UNI.BLOCK]',
    'uniforms_callbacks': '`uniforms` 的计算脚本：把参数和场景状态写进 uB 的各个槽位。源文件 ext/uniforms_chop.py。[BTDR:FILE.UNIFORMS]',
    'uniforms_callbacks1': 'TD 新建 Script CHOP 时自动带的模板回调，没有被使用（真正的回调是 uniforms_callbacks）。',
    'status': '状态文本：相机、灯、几何体的解析结果和所有警告。Render 页的 Status 参数显示它的第一条。',
    'white': '4×4 白色常量：没有贴图时给材质采样器用，也给 Debug View 当占位输入。',
    # ---------------- 场景镜像 ----------------
    'scene': '场景镜像：Refresh 时为每个 Geometry COMP 建一个镜像几何体（g* 不透明、t* 透明），材质换成 BTDR 的 G-Buffer 材质（参数用表达式绑定原 PBR MAT，不每帧重算）。不要手动改里面的东西。[BTDR:EXT.MIRROR] [BTDR:GBUF.SHARED]',
    'cam_jit': '内部相机：跟随用户相机，投影上叠加 TAA 的亚像素抖动。所有 Render TOP 都用它。[BTDR:EXT.JITCAM]',
    'suncam': '主光的阴影相机（正交）：朝向跟随第一盏平行光，范围按 Light 页的 Shadow Center / Range（或自动包围盒）。',
    'topcam': 'Height-Field AO 用的顶视正交相机，范围同阴影。',
    'mat_shadow': '画阴影图 / 顶视高度图用的材质：只输出到光源（或顶视相机）的线性距离。',
    # ---------------- G-Buffer ----------------
    'gbuffer': 'G-Buffer（延迟渲染第一步）：Render TOP，用 cam_jit 画所有不透明镜像（scene/g*），4 个颜色缓冲：0 底色|金属度，1 法线|粗糙度，2 相对相机的位置|材质 AO，3 自发光|SSS 档案编号。[BTDR:GBUF.*]',
    'gbuf0': 'G-Buffer 缓冲 0：底色 rgb | 金属度。',
    'gbuf1': 'G-Buffer 缓冲 1：世界法线 | 粗糙度。',
    'gbuf2': 'G-Buffer 缓冲 2：相对相机的位置（16 位浮点）| 材质 AO。很多屏幕空间效果从它重建深度。',
    'gbuf3': 'G-Buffer 缓冲 3：自发光 | 不透明层里存 2 + SSS 档案编号（[BTDR:GBUF.SSSID]）。',
    'gbuffer_vert': 'G-Buffer 材质的顶点着色器：位置、法线、实例颜色、贴图坐标（SOP 用 uv[0]，POP 用 Tex 属性，[BTDR:GBUF.POPUV]）。源文件 shaders/gbuffer.vert。',
    'gbuffer_frag': 'G-Buffer 材质的像素着色器：读 PBR MAT 的数值和贴图，写 4 个缓冲；透明层多写第 5 个（IOR、吸收、薄壁）。源文件 shaders/gbuffer.frag。',
    # ---------------- 主光阴影 ----------------
    'shadow': '主光阴影图：Render TOP，从 suncam 画投影物体，存到光源的线性距离。只在灯或物体变化时重画。[BTDR:SHADOW.*]',
    'shadow_cache': '阴影图缓存：场景静止时冻结上一张阴影图，`shadow` 不再计算（静止场景阴影零开销）。',
    'shadow_src': '阴影来源开关：动的时候直接用 shadow，静止时用 shadow_cache。由扩展按变化检测切换。',
    'shadow_vert': '阴影材质的顶点着色器。源文件 shaders/shadow.vert。',
    'shadow_frag': '阴影材质的像素着色器：输出线性距离。源文件 shaders/shadow.frag。',
    # ---------------- Height-Field AO ----------------
    'hf_render': 'Height-Field AO 的顶视高度图：从 topcam 往下画场景。Indirect 页 Height-Field AO 打开时才计算。',
    'hf_cache': '顶视高度图缓存：物体不动就不重画。',
    'hf_off': 'Height-Field AO 关闭时的占位常量。',
    'hf_src': 'Height-Field AO 开关（Indirect 页 Height-Field AO）。',
    # ---------------- 环境光 ----------------
    'env_studio': '内置程序化摄影棚环境（渐变 + 4 个柔光箱），Environment 页 Source = Studio 或 Auto 找不到环境灯时用。',
    'env_user': '用户的 HDRI：Source = HDRI Map 时选 HDRI Map 参数的 TOP；Auto 时选 Environment Light COMP 的贴图。',
    'env_src': '环境来源开关：摄影棚 / 用户 HDRI。',
    'env_atlas': '环境预过滤图集：把环境图按粗糙度预先模糊成几级（镜面反射用）并算出漫反射辐照度。只在环境变化时重算。[BTDR:ENV.*]',
    # ---------------- 光照与合成 ----------------
    'lighting': '只给 Debug View 用的光照分项（直接光、环境漫反射、环境镜面）。正式画面的光照在 composite 里现算，不经过它。[BTDR:COMP.INLINE]',
    'lit1': 'lighting 的缓冲 1（Debug View：环境漫反射）。', 'lit2': 'lighting 的缓冲 2（Debug View：环境镜面）。', 'lit3': 'lighting 的缓冲 3（Debug View：BRDF 项）。',
    'composite': '延迟光照 + 合成（核心）：读 G-Buffer，算太阳直接光（PCSS 软阴影）、环境光、AO、反弹光、反射、Height-Field AO、光追反射和探针 GI，输出 HDR 画面。有 SSS 物体时第 2 个输出是要散射的辐照度。[BTDR:COMP.*]',
    # ---------------- 次表面散射 ----------------
    'sss_irr': 'composite 的第 2 个输出：SSS 物体不乘底色的辐照度 | 档案编号。场景里有 SSS 物体时才存在。[BTDR:COMP.SSS]',
    'sss_h': '次表面散射第 1 步：横向可分离模糊（Burley 型曲线，跨档案或深度断层不模糊）。[BTDR:SSS.WEIGHTS]',
    'sss_v': '次表面散射第 2 步：纵向模糊，并把模糊后的漫反射替换回画面（高光保持清晰）。[BTDR:SSS.COMPOSE]',
    'sss_blur': 'sss_v 的第 2 个输出：模糊后的辐照度，只给 Debug View「Subsurface Irradiance」用。',
    'sss_src': 'SSS 开关：Subsurface 页打开且有 SSS 物体时走 sss_v，否则直接用 composite（零开销）。',
    'dbg_sss1': '挡板开关：没有 SSS 物体时给 Debug View 白图，避免拉取不存在的缓冲。',
    'dbg_sss2': '挡板开关：只有 Debug View 选 Subsurface Irradiance 时才拉取 sss_blur。',
    # ---------------- 透明与折射 ----------------
    'tgbuffer': '前景透明层的 G-Buffer：只画透明镜像（scene/t*），5 个缓冲，第 5 个是 IOR / 吸收距离 / 薄壁。有透明物体时才计算。[BTDR:M6A.*]',
    'tgbuf0': '透明层缓冲 0：底色 | 金属度。', 'tgbuf1': '透明层缓冲 1：法线 | 粗糙度。', 'tgbuf2': '透明层缓冲 2：位置 | AO。',
    'tgbuf3': '透明层缓冲 3：自发光 | 不透明度。', 'tgbuf4': '透明层缓冲 4：IOR、吸收距离、薄壁、薄壁透射提亮（0.8.1）。',
    'tback': '透明物体的背面：同样的几何体剔除正面，得到最远的背面位置和法线，用来测厚度。',
    'tback1': 'tback 的缓冲 1：背面法线。', 'tback2': 'tback 的缓冲 2：背面位置。',
    'refract': '折射合成：两次折射（进、出）、按厚度吸收（Beer-Lambert）、菲涅尔反射、按粗糙度和距离模糊（磨砂），薄壁按距离模糊（0.8.1）。输出 0 画面，1 合并后的位置，2 合并后的法线。[BTDR:REFR.*]',
    'refract1': 'refract 的缓冲 1：透明表面在前时用它的位置，给雾、TAA 用。', 'refract2': 'refract 的缓冲 2：合并后的法线。',
    'trans_src': '透明开关：有透明物体时走 refract，否则直接用不透明画面（零开销）。',
    'tpos_src': '位置来源开关：有透明物体时给雾和 TAA 合并后的位置。', 'tnrm_src': '法线来源开关：有透明物体时给 TAA 合并后的法线。',
    # ---------------- 屏幕空间 ----------------
    'ssgi': '屏幕空间 AO + 反弹光（一次地平线扫描同时得到），读上一帧画面 taa_hist。[BTDR:SS.*]',
    'ssgi_acc': 'AO / 反弹光的时间累积（去噪）。', 'ssgi_hist': 'AO / 反弹光的历史帧。', 'ssgi_off': 'AO / 反弹光关闭时的占位常量。',
    'ssgi_src': 'AO / 反弹光开关（Indirect 页 Screen-Space AO 或 Bounce Light）。',
    'ssr': '屏幕空间反射：沿反射方向在深度里步进找交点，读上一帧画面。[BTDR:SSR.*]',
    'ssr_acc': '反射的时间累积。', 'ssr_hist': '反射的历史帧。', 'ssr_off': '反射关闭时的占位常量。', 'ssr_src': '反射开关（Indirect 页 Screen-Space Reflections）。',
    # ---------------- 硬件光追 ----------------
    'rtscene': '光追代理场景：Refresh 时把几何体减面（Proxy Detail）合成一份低模，建加速结构。[BTDR:EXT.RTPROXY]',
    'rt_scene': '选出光追代理（不透明物体）。', 'rt_scene_t': '选出含玻璃的光追代理（光追折射用）。',
    'rt_mat': '光追代理的材质表：每个物体的平均颜色、自发光、透明参数（命中点着色用）。Refresh 时写入。',
    'rt_mat_chop': 'rt_mat 转成 CHOP，给 GLSL POP 当数组用。',
    'rt_static': '场景静止检测表：灯、物体、参数不变时探针 GI 不重算。[BTDR:UNI.RTSTATIC]',
    'rt_static_chop': 'rt_static 转成 CHOP。',
    'rt_probe_grid': '探针网格的点（约 2000 个，按场景形状分配）。[BTDR:EXT.RTGRIDDIMS]',
    'rt_probes': '探针 GI：每个探针向四周发光线，记下各方向来的光（球谐系数）。只在场景或灯变化时计算。',
    'probe_sh0': '探针结果转成纹理（球谐第 0 组）。', 'probe_sh1': '探针结果转成纹理（球谐第 1 组）。',
    'probe_sh2': '探针结果转成纹理（球谐第 2 组）。', 'probe_sh3': '探针结果转成纹理（球谐第 3 组）。',
    'probe_src0': '探针 GI 开关（Ray Tracing 页）。', 'probe_src1': '探针 GI 开关。', 'probe_src2': '探针 GI 开关。', 'probe_src3': '探针 GI 开关。',
    'rt_probe_off': '探针 GI 关闭时的占位。',
    'rt_refl_grid': '光追反射的发射点网格（1/4 分辨率，Low 1/6）。',
    'rt_refl': '光追反射：每个点发一条反射光线，算“实际看到的 / 环境贴图”的亮度比。[BTDR:RT.*]',
    'rt_refl_top': '光追反射结果转成纹理。', 'rt_acc': '光追反射的时间累积。', 'rt_hist': '光追反射的历史帧。',
    'rt_off': '光追反射关闭时的占位。', 'rt_src': '光追反射开关（Ray Tracing 页 Ray-Traced Reflections）。',
    'rt_refr': '光追折射：从前景透明层发光线，在玻璃代理里真的穿过去（多层玻璃、画面外）。[BTDR:REFR.RT]',
    'rt_refr_top': '光追折射结果转成纹理。', 'rt_refr_acc': '光追折射的时间累积。', 'rt_refr_hist': '光追折射的历史帧。',
    'rt_refr_off': '光追折射关闭时的占位。', 'rtr_src': '光追折射开关（Refraction Method = Hybrid / Ray Traced）。',
    # ---------------- 体积雾 ----------------
    'fog_scatter': '体积雾第 1 步（计算着色器，3D 格子）：每格的散射光（太阳 + 雾里的软阴影 + 环境）。Fog 页打开才计算。[BTDR:FOG.*]',
    'fog_accum': '体积雾第 2 步：3D 格子里的时间累积（去噪）。', 'fog_hist': '体积雾的历史。',
    'fog_integrate': '体积雾第 3 步：沿视线方向积分，得到每个深度的透过率和累积散射。',
    'fog_apply': '体积雾第 4 步：按每个像素的深度把雾叠到画面上。',
    'fog_src': '体积雾开关（Fog 页 Volumetric Fog）。',
    # ---------------- 抗锯齿与镜头 ----------------
    'taa': 'TAA 时间抗锯齿：当前帧和重投影的历史帧混合（方差裁剪防拖影）。[BTDR:TAA.*]',
    'taa_hist': 'TAA 的历史帧（上一帧结果），SSR / SSGI 也读它当“上一帧画面”。',
    'dof': '景深：按弥散圆大小模糊（Post 页 Depth of Field）。', 'post_dof': '景深开关。',
    'mblur': '运动模糊（只有相机运动）。', 'post_mb': '运动模糊开关。第 2 个输出口（HDR）就接在这里。',
    'ae_lum': '自动曝光：算画面亮度。', 'ae_avg': '自动曝光：求平均。', 'ae_hist': '自动曝光：上一帧的曝光（逐渐适应）。',
    'ae_exposure': '自动曝光：算出这一帧的曝光倍数。', 'ae_off': '自动曝光关闭时的占位。', 'ae_src': '自动曝光开关（Post 页 Auto Exposure）。',
    'bloom_pre': 'Bloom 第 1 步：曝光后按阈值提取亮部（Karis 平均防闪烁）。[BTDR:BLOOM.CHAIN]',
    'bloom_lvl': 'Quality = Low 时少算最大的两级 Bloom。',
    'bloom_off': 'Bloom 为 0 时的占位。', 'bloom_src': 'Bloom 开关（Post 页 Bloom Intensity > 0）。',
    'grade': '调色：曝光、Bloom、ACES 色调映射、暗角、颗粒、透明背景的 alpha，输出 8 位 sRGB。[BTDR:GRADE.*]',
    'depth': '第 3 个输出口的深度图：到相机平面的距离。',
    # ---------------- 调试与输出 ----------------
    'debug': 'Debug View：Render 页 Debug View 不是 Final 时显示中间结果（G-Buffer、光照分项、AO、反射、光追、SSS……）。',
    'view': '最终画面 / Debug View 切换。',
    'out_src': '封面 / 渲染画面切换：加载时显示封面，准备好后切到渲染画面（Info 页 Cover While Loading）。',
    'out1': '输出 1：最终画面（8 位 sRGB）。', 'out2': '输出 2：HDR 线性画面（Bloom 和调色之前），alpha 是视深。', 'out3': '输出 3：深度（32 位浮点）。',
    # ---------------- 封面 ----------------
    'cover': '封面 Logo 和加载动画（有向距离场绘制，tox 里没有图片）。[BTDR:BUILD.COVER]',
    'cover_title': '封面标题文字。', 'cover_status': '封面状态文字（等待相机 / 加载中）。', 'cover_credit': '封面作者文字。',
    'cover_ov0': '封面叠字。', 'cover_ov1': '封面叠字。', 'cover_ov2': '封面叠字，最终的封面画面。',
    'cover_state': '封面状态：show（是否显示）、mode（等待相机 / 加载中）。',
}

# 着色器 / 脚本 DAT：<名字> -> 源文件和一句话用途（完整说明见源文件开头的注释）
SHADER_NOTES = {
    'composite_frag': ('composite.frag', 'composite 的着色器'), 'lighting_frag': ('lighting.frag', 'lighting（Debug 用光照分项）'),
    'refract_frag': ('refract.frag', 'refract 的着色器'), 'debug_frag': ('debug.frag', 'Debug View'),
    'taa_frag': ('taa.frag', 'TAA'), 'grade_frag': ('grade.frag', '调色'), 'depth_frag': ('depth.frag', '深度输出'),
    'dof_frag': ('dof.frag', '景深'), 'mblur_frag': ('mblur.frag', '运动模糊'),
    'bloom_pre_frag': ('bloom_pre.frag', 'Bloom 亮部提取'), 'bloom_karis_frag': ('bloom_down.frag + Karis', 'Bloom 第一级下采样（防闪烁）'),
    'bloom_down_frag': ('bloom_down.frag', 'Bloom 下采样'), 'bloom_up_frag': ('bloom_up.frag', 'Bloom 上采样'),
    'lum_frag': ('lum.frag', '自动曝光测光'), 'exposure_frag': ('exposure.frag', '自动曝光'),
    'ssgi_frag': ('ssgi.frag', 'AO + 反弹光'), 'ssr_frag': ('ssr.frag', '屏幕空间反射'), 'ss_accum_frag': ('ss_accum.frag', '屏幕空间效果的时间累积'),
    'env_studio_frag': ('env_studio.frag', '程序化摄影棚'), 'env_prefilter_frag': ('env_prefilter.frag', '环境预过滤'),
    'fog_scatter_comp': ('fog_scatter.comp', '体积雾散射'), 'fog_accum_comp': ('fog_accum.comp', '体积雾累积'),
    'fog_integrate_comp': ('fog_integrate.comp', '体积雾积分'), 'fog_apply_frag': ('fog_apply.frag', '体积雾叠加'),
    'rt_probes_comp': ('rt_probes.comp', '探针 GI'), 'rt_refl_comp': ('rt_refl.comp', '光追反射'), 'rt_refr_comp': ('rt_refr.comp', '光追折射'),
    'rt_accum_frag': ('rt_accum.frag', '光追结果的时间累积'),
    'sss_frag': ('sss.frag', 'SSS 横向模糊'), 'sss_v_frag': ('sss.frag（SSS_V）', 'SSS 纵向模糊 + 合成'),
    'cover_frag': ('cover.frag', '封面 Logo'), 'white_frag': ('（内置）', '纯白'), 'zero_frag': ('（内置）', '纯黑 / 0'),
}

# 分组框：标题、成员、颜色
GROUPS = [
    ('脚本与控制：扩展、参数回调、场景监视', ['BTDRExt', 'parexec', 'execute', 'scene_watch', 'cover_warm', 'uniforms_callbacks', 'status'], (0.35, 0.35, 0.45)),
    ('场景镜像与相机：Refresh 时重建，不要手动改', ['scene', 'cam_jit', 'uniforms', 'white'], (0.3, 0.4, 0.3)),
    ('G-Buffer：延迟渲染第一步，4 个缓冲', ['gbuffer', 'gbuf0', 'gbuf1', 'gbuf2', 'gbuf3'], (0.25, 0.35, 0.5)),
    ('主光阴影：只在变化时重画', ['suncam', 'shadow', 'shadow_cache', 'shadow_src', 'mat_shadow'], (0.4, 0.35, 0.25)),
    ('Height-Field AO：顶视高度图', ['topcam', 'hf_render', 'hf_cache', 'hf_src', 'hf_off'], (0.4, 0.35, 0.25)),
    ('环境光：摄影棚 / HDRI / 环境灯，预过滤', ['env_studio', 'env_user', 'env_src', 'env_atlas'], (0.25, 0.4, 0.45)),
    ('透明层：前景 G-Buffer + 背面测厚度', ['tgbuffer', 'tgbuf0', 'tgbuf1', 'tgbuf2', 'tgbuf3', 'tgbuf4', 'tback', 'tback1', 'tback2'], (0.3, 0.3, 0.5)),
    ('折射合成与透明开关', ['refract', 'refract1', 'refract2', 'trans_src', 'tpos_src', 'tnrm_src'], (0.3, 0.3, 0.5)),
    ('屏幕空间反射 SSR', ['ssr', 'ssr_acc', 'ssr_hist', 'ssr_off', 'ssr_src'], (0.4, 0.3, 0.4)),
    ('屏幕空间 AO + 反弹光', ['ssgi', 'ssgi_acc', 'ssgi_hist', 'ssgi_off', 'ssgi_src'], (0.4, 0.3, 0.4)),
    ('体积雾：散射 → 累积 → 积分 → 叠加', ['fog_hist', 'fog_accum', 'fog_scatter', 'fog_integrate', 'fog_apply'], (0.35, 0.35, 0.35)),
    ('硬件光追：代理、探针 GI、反射、折射', ['rt_scene', 'rt_scene_t', 'rt_mat_chop', 'rt_static_chop', 'rt_probe_grid', 'rt_probes',
        'probe_sh0', 'probe_sh1', 'probe_sh2', 'probe_sh3', 'probe_src0', 'probe_src1', 'probe_src2', 'probe_src3', 'rt_off',
        'rt_refl_grid', 'rt_refl', 'rt_refl_top', 'rt_probe_off', 'rt_acc', 'rt_src', 'rt_hist', 'rt_refr_off',
        'rt_refr', 'rt_refr_top', 'rt_refr_acc', 'rtr_src', 'rt_refr_hist'], (0.45, 0.3, 0.25)),
    ('自动曝光', ['ae_hist', 'ae_lum', 'ae_avg', 'ae_exposure', 'ae_src', 'ae_off'], (0.4, 0.4, 0.25)),
    ('Bloom：6 级下采样 + 上采样', ['bloom_pre', 'bloom_d1', 'bloom_d2', 'bloom_d3', 'bloom_d4', 'bloom_d5', 'bloom_d6',
        'bloom_u0', 'bloom_u1', 'bloom_u2', 'bloom_u3', 'bloom_u4', 'bloom_u5', 'bloom_lvl', 'bloom_off', 'bloom_src'], (0.4, 0.4, 0.25)),
    ('主链：合成 → TAA → 调色 → 输出', ['composite', 'taa', 'grade', 'view', 'out1', 'out2', 'out3', 'depth', 'debug', 'taa_hist',
        'lighting', 'lit1', 'lit2', 'lit3', 'fog_src', 'dbg_sss1', 'dbg_sss2'], (0.5, 0.45, 0.2)),
    ('着色器源码（由 build.py 生成，改 btdr/shaders/ 里的源文件）', None, (0.3, 0.3, 0.3)),   # None = 所有 *_frag / *_comp / *_vert
]

OVERVIEW_TITLE = 'BetterTDRender 内部结构总览（%s）'
OVERVIEW = """这是 renderBTDR 的内部网络。正常使用不需要进来：所有设置都在组件的参数页上。
每个节点都写了注释（节点 Comment）；同一功能的节点用框圈起来，框的标题写它做什么。
文字里的 [BTDR:...] 是文档锚点，在 btdr/docs/IMPLEMENTATION*.md 里搜索可以找到实现细节。

一帧的数据流（从上游到下游）：
1. uniforms：把相机、灯、全部参数写进一个共享数组 uB，所有着色器读它。
2. scene（镜像）+ cam_jit（带 TAA 抖动的相机）→ gbuffer：画出 4 张 G-Buffer（底色、法线、位置、自发光）。
3. 并行准备：shadow（主光阴影，静止时缓存）、env_atlas（环境预过滤）、ssgi / ssr（屏幕空间 AO、反弹光、反射，读上一帧）、
   rt_*（硬件光追：探针 GI、光追反射）、hf_*（Height-Field AO）。
4. composite：用上面所有结果算光照，得到 HDR 画面。
5. sss_h → sss_v：有次表面散射物体时，把漫反射在屏幕上散开（没有则跳过）。
6. tgbuffer / tback → refract：有透明物体时，画前景透明层、测厚度、算折射（没有则跳过）。
7. fog_*：体积雾（Fog 页打开时）。
8. taa → dof → mblur：抗锯齿、景深、运动模糊。第 2 个输出口（HDR）在这里。
9. ae_*、bloom_*：自动曝光、Bloom。
10. grade：调色、色调映射 → view（Debug View 切换）→ out_src（封面切换）→ out1。

读法提示：
- 名字以 _src 结尾的 Switch 是效果开关，关闭的效果整条链不计算（零开销）。
- 名字以 _hist 结尾的 Feedback 是上一帧的历史，用于时间累积去噪。
- 名字以 _off 结尾的常量是效果关闭时的占位输入。
- 想看中间结果：Render 页的 Debug View，比进来看节点方便。
- 不要手动修改 scene / rtscene 里的内容：Refresh 时会重建。
- 这个网络由 btdr/build.py 生成；改着色器请改 btdr/shaders/ 里的源文件，再运行 build.py。"""


def annotate(C, version, log):
    """在组件 C 里加注释。只加 annotateCOMP 和节点 Comment，不改节点位置和连线。"""
    shader_types = ('_frag', '_comp', '_vert')
    n_notes = 0
    for c in C.children:
        txt = NOTES.get(c.name)
        if txt is None and c.name in SHADER_NOTES:
            src, what = SHADER_NOTES[c.name]
            txt = '着色器源码：%s。由 build.py 从 btdr/shaders/%s 生成（前面拼了 common.glsl 等公共代码）；要改请改源文件再构建。' % (what, src)
        if txt is None and c.name.startswith('bloom_d'):
            txt = 'Bloom 下采样第 %s 级（13 点滤波，每级尺寸减半）。' % c.name[7:]
        if txt is None and c.name.startswith('bloom_u'):
            txt = 'Bloom 上采样第 %s 级（3×3 帐篷滤波，叠加下一级的结果；Bloom Radius 控制各级权重）。' % c.name[7:]
        if txt:
            try:
                c.comment = txt
                n_notes += 1
            except Exception:
                pass
    # 分组框：成员的外接框加边距；框里混进别组节点就跳过（不移动节点）
    kids = [c for c in C.children if c.OPType != 'annotateCOMP']
    boxes, skipped = 0, []
    M = 50
    for title, names, col in GROUPS:
        if names is None:
            mem = [c for c in kids if c.family == 'DAT' and c.name.endswith(shader_types)]
        else:
            mem = [C.op(n) for n in names if C.op(n) is not None]
        if not mem:
            continue
        x0 = min(c.nodeX for c in mem) - M
        y0 = min(c.nodeY for c in mem) - M
        x1 = max(c.nodeX + c.nodeWidth for c in mem) + M
        y1 = max(c.nodeY + c.nodeHeight for c in mem) + M + 40          # 40：标题栏
        ids = set(c.id for c in mem)
        intruders = [c.name for c in kids if c.id not in ids
                     and x0 < c.nodeX + c.nodeWidth / 2 < x1 and y0 < c.nodeY + c.nodeHeight / 2 < y1]
        if intruders:
            skipped.append('%s（框内有 %s）' % (title.split('：')[0], ', '.join(intruders[:4])))
            continue
        a = C.create(annotateCOMP, 'note_%02d' % boxes)
        a.par.Mode = 'networkbox'
        a.par.Titletext = title
        a.par.Backcolorr, a.par.Backcolorg, a.par.Backcolorb = col
        a.par.Backcoloralpha = 0.35
        a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight = x0, y0, x1 - x0, y1 - y0
        boxes += 1
    # 总览面板：放在所有节点左边
    left = min(c.nodeX for c in kids)
    top = max(c.nodeY + c.nodeHeight for c in kids)
    a = C.create(annotateCOMP, 'note_overview')
    a.par.Mode = 'annotate'
    a.par.Titletext = OVERVIEW_TITLE % version
    a.par.Bodytext = OVERVIEW
    a.par.Bodyfontsize = 12
    a.par.Backcolorr, a.par.Backcolorg, a.par.Backcolorb = 0.12, 0.12, 0.14
    a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight = left - 1500, top - 1300, 1350, 1300
    log.append('annotations: %d node comments, %d group boxes, overview; skipped boxes: %s'
               % (n_notes, boxes, '; '.join(skipped) or 'none'))
