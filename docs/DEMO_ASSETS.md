# BTDR 示例场景和测试素材

从 `IMPLEMENTATION.md` 移出来的素材说明：真实 HDRI 测试、示例场景的贴图（§11c）、测试模型（§11d）。`DEMO.*` 锚点在 `examples/demo_scene.py`。

## 真实 HDRI 测试

真实 HDRI 另外手动测过一次（2026-11-11）：Poly Haven 的 `kloofendal_43d_clear` 2K（CC0，晴天带太阳，`btdr/examples/hdri/kloofendal_43d_clear_2k.hdr`，6.1 MB）。
源图最大亮度 110080（太阳），超过 100 的像素 53 个；预滤波图集无 NaN，各层最大值 371 / 26.6 / 7.8 / 4.1 / 2.8，辐照度层平均 0.85；画面无报错无警告，没有看到闪烁噪点。
做法：找出全景图里最亮像素的方向，让 Light COMP 和它对齐，阴影就和 HDRI 里的太阳一致。
示例场景用的是反过来的做法：灯不动，用 Environment Rotate 转 HDRI（太阳在 u = 0.600、仰角 43°，灯是 rx −45.3、ry 47.7，算出 Rotate = −96.2，见 `DEMO.HDRI`）。
换算：方向 d 的 u = atan2(d′x, −d′z)/2π + 0.5，d′ 是 d 绕 y 转 Rotate；所以 Rotate 每加 1° 太阳的 u 加 1/360。
注意 HDRI 里的太阳同时进了环境漫反射（不带阴影），再叠加 Light COMP 的直接光，所以影子比真实晴天浅；要更实的影子就降低 Environment Intensity 或提高灯的 Dimmer。

## 11c. 示例场景的贴图（`examples/demo_scene.py`）

- `DEMO.TEXLIB`：贴图集中在 `/project1/tex_lib`（`bc_i`、`ao_i`、`rough_i`、`metal_i`、`nrm_i`，i 是模型按文件名排序的序号），示例场景和原生对照组 `td_native` 共用，一份显存。
- 原始贴图（2026-11-12 迁入 `模型_简化`）：四件文物都有 4K 的 roughness / metallic / normal。基础色原图是 8K，`_basecolor_4k.jpg` 与原图缩小后的相关系数为 1.0，所以 UV 和简化模型对得上。
  人形车辖、鎏金铜兽形饰按原贴图基本是非金属（金属度平均 0.04 / 0.13）、很粗糙（0.91 / 0.98）；金印、造像以金属为主。
- 法线约定：模型来自 Tripo、用 Blender 导出，按 OpenGL（Y+）读取。用两种统计方法验证都没有结论：
  ① 与原始 200 万面高模比较——高模本身很光滑（与简化模型法线只差 1.9°），细节全在法线贴图里，相关系数两种约定都约为 0；
  ② 傅里叶域旋度占比——四张贴图两票对两票，说明这些 AI 生成的法线贴图不是严格的高度场梯度。
  掠射光下的对比图差别也很小。结论：按工具默认约定（OpenGL）使用。0.1.2 在 Render 页加了 Normal Map Convention 开关。
- 法线强度（PBR MAT 的 Bump Scale）默认 **0.2**。Tripo 把同样的起伏既做进了模型几何、又烘进了法线贴图，相当于叠加两遍：贴图法线与几何法线平均偏差约 17°，按 1.0 使用表面会像融化或锤打过一样。实测 0.15–0.3 能保留细节，0.5 以上开始出现鼓包（对比图 `btdr_normal_strength_sweep.jpg`）。
- 鎏金铜造像的原始金属度贴图不可用：按 UV 块随机分布，和基础色里的鎏金区域基本无关（金色像素的平均金属度只有 0.59，整体只有 51% 是金属；对照金印是 94%）。
  `DEMO.GILT`：改用从基础色推出来的 `鎏金铜造像_metallic_gilt.png`（金黄色调、够亮、够饱和的像素 = 金属，锈斑和蓝黑色头发 = 非金属，2 像素模糊），原始贴图保留不动。示例场景优先读 `_gilt` 版本。
- 原生对照组 `td_native` 不挂法线贴图：原生 PBR MAT 加上这些法线贴图会渲染成黑色（推测是模型缺少切线属性）。
- `DEMO.TESTMODELS`（2026-11-12 起的默认场景）：`测试模型/` 里有 AntiqueCamera 和 FlightHelmet 时，示例场景改用它们（相机高 1.5、头盔高 0.95，并排放），每个材质部件一个 Geometry COMP + PBR MAT，法线强度 1；否则退回 `模型_简化` 的文物模型。
  每个部件在 File In SOP 后面接一个 Attribute Create SOP 算 MikkTSpace 切线：原生 PBR MAT 的法线贴图需要切线，没有切线时整个物体渲染成黑色（之前 `td_native` 发黑就是这个原因）；BTDR 用屏幕空间导数算切线，不需要它。
- `DEMO.NATIVE`：示例场景里自带原生对照组 `native_render`（同一套 Geometry COMP、材质和贴图，加一盏用同一张 HDRI 的 Environment Light），不额外占显存；`tools/perf_bench.py` 用它做对比。旧的独立对照组 `td_native` 已删除。
- `DEMO.HDRI`：有 `examples/hdri/kloofendal_43d_clear_2k.hdr` 时，示例场景用它做环境和背景，Rotate −96.2（太阳和 light1 对齐），Background Blur 0.1（背景略虚，主体更突出）。
- 教训：**不要在正在使用的工程里加载原始高模**（137 MB OBJ）。2026-11-12 这样做导致 TouchDesigner 崩溃；高模分析改在云端工作区离线做。

## 11d. 测试模型（工程目录 `测试模型/`）

2026-11-12 起替换掉质量不够的 Tripo 文物模型，来自 Khronos glTF Sample Assets（GitHub），用 `tools/gltf2obj.py` 转成 OBJ + 分离贴图，每个文件夹里有 `README_license.md` 和 `convert_report.json`。

| 模型 | 许可 | 用途 |
|---|---|---|
| DamagedHelmet | CC BY 4.0（早期版本 CC BY-NC 4.0，商用前要确认） | 全套贴图：基础色、金属度、粗糙度、AO、法线、自发光 |
| AntiqueCamera | CC0 | 黄铜、皮革、木头，旧金属质感，接近文物题材 |
| FlightHelmet | CC0 | 6 种材质（皮革、金属、橡胶、木头、玻璃镜片——透明还不支持，按不透明画） |
| MetalRoughSpheres | CC BY 4.0 | 金属度 × 粗糙度的标定球阵，用来核对 BRDF |
| ABeautifulGame | CC BY 4.0 | 国际象棋整盘，15 种材质，多物体阴影；兵的顶部是玻璃（不支持） |
| CarConcept | CC BY 4.0（Eric Chadwick / Darmstadt Graphics Group，2024；基于 Sketchfab 上 Unity Fan 的 CC0 模型）。使用时要署名，见文件夹里的 `CREDITS.txt` | 概念超跑，21 万三角面、23 种材质：车漆、镀铬轮毂、刹车卡钳、车灯自发光、深色玻璃。用 `MODEL = 'CarConcept'` 载入 `model_preview.py`，场景在 `/project1/btdr_models/CarConcept` |

转换注意：glTF 的 v 坐标从上往下，OBJ 从下往上，所以写 `1 − v`；glTF 法线贴图是 OpenGL（Y+）约定；ORM 贴图 R = AO、G = 粗糙度、B = 金属度。


CarConcept 用到了 BTDR 还不支持的 glTF 扩展，`gltf2obj.py` 转换时这样处理（2026-11-12 起对所有模型生效，记在 `convert_report.json` 的 `note` / `dropped`）：
- 透射（KHR_materials_transmission，车窗玻璃）→ 不透明的深色光滑材质（基础色 0.02、粗糙度 0.03），看起来像贴膜玻璃，反射照常。
- 用第二套 UV 的贴图（这辆车的 AO 全在 UV1 上）和带 KHR_texture_transform 平铺 / 偏移的贴图（车漆金属闪片、内饰布纹、轮胎花纹、刹车盘的法线和颜色）→ 不导出，只用数值。否则 AO 会变成错位的污渍，平铺的法线会被拉成一整块。
- KHR_materials_emissive_strength 乘进自发光颜色（车灯）。没有贴图的纯数值自发光由 `model_preview.py` 直接写进 PBR MAT 的 Emit（以前只在有贴图时才设置，车灯不亮）。
- 清漆层（clearcoat）、彩虹色（iridescence）、材质变体（只用默认的 Carmine Candy 红色）不支持。

这辆车上看到的两个画质问题（未修）：低机位看光滑地面时，屏幕空间反射在掠射角有横向阶梯条纹；夜景里很亮的小光源（车灯）周围的 Bloom 呈方块状。
