# BTDR 性能记录（历史）

从 `IMPLEMENTATION_2.md` §10 移出来的旧版本实测，方法同 §10。最新一版的数字在 §10。

0.1.2 实测（2026-11-12，5080 Laptop）：

| 情况 | GPU 中位数 | CPU 中位数 |
|---|---|---|
| TD 原生 Render TOP（PBR MAT、一盏平行光软阴影 + 环境光），1080p | 1.69 ms | 0.60 ms |
| BTDR High，1080p | 1.05 ms | 1.25 ms |
| BTDR Low，1080p | 0.84 ms | 1.21 ms |
| BTDR High，1440p | 1.48 ms | 1.27 ms |
| BTDR High，2160p | 2.72 ms | 1.23 ms |

（下面两张表是阴影缓存之前的数据；缓存之后的结果见本节末尾。）

GPU 分项（High，1080p）：`gbuffer` 0.36、`shadow` 0.28、`lighting` 0.17、4 个 `gbufN` 合计约 0.13、其余约 0.05。
CPU 分项（`tools/cpu_profile.py`）：`gbuffer` 0.46、`shadow` 0.25、`uniforms` 0.22（含它触发的 `suncam` 计算）、`lighting` 0.11、其余约 0.3。镜像材质不再每帧计算。

和 0.1.1（GPU 1.55 / CPU 1.65）相比：
- G-Buffer 从 `rgba32float` 改 `rgba16float`（位置改存相对相机坐标）：`gbuffer` 0.60 → 0.36，4 个 Render Select 的复制 0.33 → 0.13。
- 镜像材质的抖动改读 `jitter` CHOP：材质不再每帧计算，约 −0.18 ms CPU。
- `SunLocal()` 去掉 numpy 并缓存：`suncam` 计算 0.21 → 0.03 ms。`uniforms` 回调也改成纯 Python 读 `Matrix.vals`。
- 在这个 60 万三角形的旧场景里 **GPU 比原生 Render TOP 低约 40%**（新场景的结论不同，见下）；CPU 1.25 ms，在 1.5 ms 预算内，但仍是原生的约 2 倍，主要是两次 Render TOP 提交（约 0.7）。

新示例场景（2026-11-12 起：AntiqueCamera + FlightHelmet，11.5 万三角形、8 个材质、9 个 Geometry COMP，原生对照组是同一场景里的 `native_render`）：

| 情况 | GPU 中位数 | CPU 中位数 |
|---|---|---|
| TD 原生 Render TOP，1080p | 0.76 ms | 0.89 ms |
| BTDR High，1080p | 1.19 ms | 1.66 ms（`cpu_profile.py` 稳态 1.41） |
| BTDR Low，1080p | 0.96 ms | 1.55 ms |
| BTDR High，1440p | 1.28 ms | 1.35 ms |
| BTDR High，2160p | 2.06 ms | 1.37 ms |

结论要分场景看：三角形多（旧场景 60 万）时 BTDR 的 GPU 比原生低，因为光照只按像素算一次；三角形少、物体多时原生更便宜，BTDR 多出的是 G-Buffer 之后的全屏阶段（约 0.4 ms）和每个物体两次提交的 CPU。
CPU 在新场景贴着 1.5 ms 预算：Geometry COMP 从 5 个变成 9 个，两次 Render TOP 的提交随物体数增加；`suncam` 的表达式每帧还要计算约 0.1 ms。

**阴影缓存之后（同一新场景，静态灯光和物体、相机环绕）：**

| 情况 | GPU 中位数 | CPU 中位数 |
|---|---|---|
| TD 原生 Render TOP，1080p | 0.67 ms | 0.44 ms |
| BTDR High，1080p | 0.61 ms | 0.73 ms |
| BTDR Low，1080p | 0.52 ms | 0.70 ms |
| BTDR High，1440p | 0.81 ms | 0.69 ms |
| BTDR High，2160p | 1.61 ms | 0.81 ms |

`tools/cpu_profile.py` 稳态 CPU 0.67 ms：`gbuffer` 0.25、`uniforms` 0.21、`lighting` 0.06，其余都很小。灯光或物体在动时阴影图每帧重画，回到上面"缓存之前"的数字（GPU 约 1.2 ms、CPU 约 1.4 ms）。
（Render TOP 的 CPU 也跟着降了：不画阴影图后 `gbuffer` 从 0.49 降到 0.25，推测两次 Render TOP 共享了一部分每帧的场景准备开销。）

**0.2.0（M2）实测（2026-11-12，同一新场景，相机环绕、灯光和物体静止，同一时段测）：**

| 情况 | GPU 中位数（去掉 gbuf0 等待） | CPU 中位数 |
|---|---|---|
| TD 原生 Render TOP，1080p | 0.71 ms | 0.47 ms |
| BTDR High，1080p，镜头效果全关 | 0.62 ms | 0.82 ms |
| BTDR High，1080p，默认（TAA + Bloom 0.05） | 0.69 ms | 0.84 ms |
| BTDR High，1080p，全开（TAA、Bloom、自动曝光、景深、运动模糊） | 1.25 ms | 0.88 ms |
| BTDR Low，1080p，全开 | 0.99 ms | 0.90 ms |
| BTDR High，1440p，默认 | 1.12 ms | 0.90 ms |
| BTDR High，2160p，默认 | 2.29 ms | 0.82 ms |

- GPU 分项（1080p）：`dof` 0.51（Low 0.32）、`taa` 0.13、`mblur` 0.07、Bloom 和自动曝光各约 0.02–0.04。
- 未扣除时的 GPU 中位数是 2.4–4.0 ms，多出来的全在 `gbuf0` 上（等 GPU 队列，§11 第 17 条）；同一天更早一次测量里这个等待是 0.5 ms，再早是 7 ms，和 BTDR 的设置无关。
- 测 CPU 时要注意机器状态：同一天里原生 Render TOP 的 CPU 读数在 0.44–0.88 ms 之间漂，所以只比较同一时段的数字。
- 在 bench 里，BTDR 各情况运行时把 light1 的原生阴影关掉（`BENCH.SYNC` 旁边的注释），否则它每帧自画的阴影图会算到 BTDR 头上（§11 第 18 条）。


**0.3.2 实测（2026-11-12，同一场景，相机环绕、灯光和物体静止，同一时段测）：**

| 情况 | GPU 中位数（去掉 gbuf0 等待） | CPU 中位数 |
|---|---|---|
| TD 原生 Render TOP，1080p | 0.71 ms | 0.92 ms |
| BTDR High，1080p，全部关闭 | 0.64 ms | 1.61 ms |
| BTDR High，1080p，默认（TAA、Bloom、AO、反弹光、反射） | 1.91 ms | 1.93 ms |
| BTDR Low，1080p，默认 | 0.90 ms | 2.13 ms |
| BTDR High，1080p，默认 + 体积雾 | 2.28 ms | 2.38 ms |
| BTDR Low，1080p，默认 + 体积雾 | 0.99 ms | 2.41 ms |
| BTDR High，1080p，全开 | 2.71 ms | 2.06 ms |
| BTDR High，1440p，默认 | 3.64 ms | 2.27 ms |
| BTDR High，2160p，默认 | 8.37 ms | 2.11 ms |

- 机器处在"慢"的状态（原生 Render TOP CPU 0.92 ms，快时 0.47 ms），CPU 只适合相互比较；`gbuf0` 等待这次是 3.6–4.8 ms。
- 体积雾逐节点 GPU（测试场景单独计时）：`fog_scatter` 0.056、`fog_accum` 0.025（0.3.2 新增）、`fog_integrate` 0.012、`fog_apply` 0.026，合计约 0.12 ms。上表 High 档"+ 体积雾"多出的 0.37 ms 大部分是测量波动（Low 档同样的雾只多 0.09 ms）。
- 0.3.2 起 `uniforms` 每帧计算（之前相机静止时不算）：相机在动的示例场景里本来就每帧算，数字不受影响。
