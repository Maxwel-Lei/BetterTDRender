BetterTDRender (BTDR) 0.5.1
===========================

A TouchDesigner render node with UE5-style rendering: PBR, soft shadows, HDRI lighting,
TAA, bloom, auto exposure, depth of field, motion blur, AO, bounce light, reflections,
volumetric fog and hardware ray tracing (probe GI + traced reflections).

Files
  BTDR.tox           the render node (renderBTDR). Self-contained.
  BTDR_Example.tox   a ready-made example network. Drop it in, open it, view OUT.
  USER_GUIDE.md      the user manual (Chinese). Start with section 2 (5-minute quick start).
  hdri/              a sunny HDRI panorama to try the HDRI environment with.

Requirements
  TouchDesigner 2025.33230 or newer, Windows.
  GPU: RTX 4060 Laptop recommended (Quality = High), RTX 2060 minimum (Quality = Low).
  Ray tracing needs an RTX 20 series or newer card; without it, it switches itself off.

Quick start
  1. Make a Camera COMP (cam1), a Distant Light COMP and a Geometry COMP with a PBR MAT.
  2. Drop BTDR.tox into the same network.
  3. Connect its output to a Null TOP. No parameters to fill in.

License
  MIT (see LICENSE). Source: https://github.com/Maxwel-Lei/BetterTDRender

Credits
  hdri/kloofendal_43d_clear_2k.hdr  Poly Haven (polyhaven.com), CC0.
  Algorithms follow published work: Jimenez 2014 (bloom), Karis 2013/2014 (PBR, TAA),
  ground-truth AO / horizon-based GI, Wronski 2014 / Hillaire 2015 (volumetric fog).
