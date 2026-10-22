"""scene.py: assemble the .blend in Blender 5.2 (filmkit.blender) and save build/film.blend.

  blender -b --python-exit-code 1 --factory-startup -P <ENGINE>/filmkit/blender/gpu.py -P scene.py

Builds slabs, tiles and screens from the timeline layout (scene_kit), the hero from hero_spec.HERO
(blender/hero), the camera (render.camera_object); bakes one key per frame from motion.hero_pose,
motion.tile_state and shots.camera_state (bake.Bake); applies look.LOOK (render.apply_look, which also
stores the look in the .blend for stills.py); saves with relative paths. The final render path is
renders/frames/. Mechanical: every value comes from the project modules.
"""
import sys
sys.dont_write_bytecode = True
import os
import time as _time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]

import bpy  # noqa: E402

from filmkit import timebase  # noqa: E402
from filmkit.blender import bake, geo, hero as hero_mod, materials, render, scene_kit  # noqa: E402
import look as LK  # noqa: E402
import motion as M  # noqa: E402
import shots as S  # noqa: E402
import timeline as T  # noqa: E402
from hero_spec import HERO  # noqa: E402


def main():
    t_start = _time.perf_counter()
    os.chdir(HERE)                                  # image paths below are project-relative
    doc, layout = scene_kit.load_timeline(HERE)
    n_frames = doc["format"]["frames"]
    sc = bpy.context.scene
    scene_kit.clear_scene(sc)
    render.setup_render(sc, LK.LOOK["preset"], LK.LOOK["presets"], film=T.FORMAT.film, fps=T.FPS, frames=n_frames,
                        view=LK.LOOK["view"]["transform"], look=LK.LOOK["view"]["look"],
                        exposure=LK.LOOK["view"]["exposure"], shutter=LK.LOOK["shutter"], persistent=True,
                        bounces=LK.LOOK.get("bounces"), out_path="//../renders/frames/")

    # the set: slabs, tiles, screens
    coll = geo.collection("Set", sc)
    scr = LK.LOOK["materials"]["screen"]
    ui_mat = materials.make_screen_material("ui", os.path.join("build", "ui.png"), scr["strength"], spec=scr["spec"],
                                            rough=scr["rough"])
    side = LK.LOOK["materials"]["side"]
    side_mat = materials.make_side_material("side", side["base"], side["specular"], side["roughness"])
    slabs = scene_kit.build_slabs(layout, T.Z["slab"], 0.0, ui_mat, side_mat, coll, bevel=T.Z["bevel"])
    tiles = scene_kit.build_tiles(layout, T.Z["tile"][0], T.Z["tile"][1], ui_mat, side_mat, coll, slabs)
    sequences = {name: (os.path.join("build", "comp", "0001.png"), n_frames) for name in layout.screens}
    scene_kit.build_screens(layout, T.Z["screen"], sequences, coll, slabs, strength=scr["strength"],
                            spec=scr["spec"], rough=scr["rough"])      # grades: apply_look reads LOOK['grades']
    tile_rest = {bid: tuple(ob.location) for bid, ob in tiles.items()}

    # the hero and the camera
    hero_coll = geo.collection("Hero", sc)
    mats = {}
    for role in HERO["materials"]:
        v = LK.LOOK["materials"][role]
        mats[role] = materials.make_toy_material(f"hero_{role}", v["base"], v["roughness"], v["specular"],
                                                 v.get("coat", 0.0), v.get("coat_roughness", 0.15))
    rig = hero_mod.build_hero(HERO, hero_coll, mats)
    cam = render.camera_object(sc, "camera", 36.0, S.SHOTS[0].lens)
    print(f"scene: built {len(bpy.data.objects)} objects in {_time.perf_counter() - t_start:.1f} s")

    # bake every frame
    B = bake.Bake(n_frames)
    for f in range(1, n_frames + 1):
        t = timebase.time(f, T.FPS)
        hero_mod.pose_channels(rig, M.hero_pose(t), f, B)
        for bid, ob in tiles.items():
            st = M.tile_state(bid, t)
            rx, ry, rz = tile_rest[bid]
            B.vec(ob, "location", f, (rx, ry, rz - st["depth"]))
            B.prop(ob, "ui_glow", f, st["glow"])
        for idb, path, value, index, interp in scene_kit.camera_channels(cam, S.camera_state(t)):
            B.put(idb, path, f, value, index, interp)
    keyed, constant = B.write()

    render.apply_look(sc, LK.LOOK, LK.REGISTRY)
    cyc = sc.objects.get(LK.REGISTRY["cyc"][0])
    if cyc is not None:
        cyc.pass_index = LK.STUDIO_INDEX
    scene_kit.summary(sc, (keyed, constant))
    info = render.save_blend(os.path.join(HERE, "build", "film.blend"))
    print(f"scene: saved build/film.blend in {_time.perf_counter() - t_start:.1f} s; {info['objects']} objects; "
          f"non-relative image paths: {info['non_relative'] or 'none'}")
    if info["non_relative"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
