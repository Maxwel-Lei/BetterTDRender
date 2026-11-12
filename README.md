# BetterTDRender (BTDR)

A single TouchDesigner operator, `renderBTDR`, that renders like Unreal Engine 5's defaults:
a deferred pipeline with PBR (native PBR MAT), soft shadows, studio / HDRI image-based lighting,
TAA, bloom, auto exposure, depth of field, motion blur, screen-space AO / bounce light / reflections,
volumetric fog, and hardware ray tracing (probe GI + traced reflections, a simplified Lumen).

![example](docs/images/example.jpg)

**Private repository.** Tag `v0.1.0` = first snapshot (internal build version 0.5.0, milestone M5).

## Quick start

1. Make a Camera COMP `cam1`, a Distant Light COMP and a Geometry COMP with a PBR MAT.
2. Drop `release/BTDR.tox` into the same network.
3. Connect its output to a Null TOP. No parameters to fill in.

Or drop `release/BTDR_Example.tox` in and view its `OUT`.

Requirements: TouchDesigner 2025.33230+, Windows, RTX 4060 Laptop recommended (RTX 2060 minimum, Quality = Low).
Ray tracing needs an RTX 20 series or newer card and switches itself off otherwise.

## Docs (Chinese)

| File | For |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Users: quick start, every parameter, performance tips |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | Maintainers: structure, anchors `[BTDR:XXX]`, every pass (§0–§9d) |
| [docs/IMPLEMENTATION_2.md](docs/IMPLEMENTATION_2.md) | Maintainers: performance, pitfalls, tests, developer workflow, changelog (§10–§13) |

## Layout

```
build.py        builds release/BTDR.tox from shaders/ and ext/ (sources are files, the .tox is a product)
shaders/        GLSL (common.glsl is prepended; *.comp are compute shaders)
ext/            Python extension, uniforms Script CHOP callbacks
tests/          m1_tests.py (39 regression checks), m5_acceptance.py (7 acceptance checks)
examples/       demo_scene.py (dev scene), make_example.py (BTDR_Example.tox), hdri/ (CC0)
tools/          perf_bench, cpu_profile, hotswap, make_release, ...
release/        BTDR.tox, BTDR_Example.tox
```

All scripts run inside TouchDesigner's Textport with the project folder as the parent of this folder
(`project.folder + '/btdr/...'`); see IMPLEMENTATION_2.md §11c.

## Credits

`examples/hdri/kloofendal_43d_clear_2k.hdr` — Poly Haven, CC0.
