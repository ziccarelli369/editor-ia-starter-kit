"""filmkit.blender: modules that import bpy. Run only inside Blender 5.2 (python 3.13).

Every headless call passes gpu.py first:
  blender -b --python-exit-code 1 --factory-startup -P <engine>/filmkit/blender/gpu.py -P <project>/scene.py -- <args>
Owners: blender-build (gpu, bake, geo, hero), blender-look (materials, render, stills, lookdev, scene_kit).
"""
