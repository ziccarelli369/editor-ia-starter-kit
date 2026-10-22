"""check_blender_look.py: quick check of the blender-look modules on the GPU. Standard library only.

Runs look_scene_blender.py inside Blender (env BLENDER or the 5.2 default) with gpu.py first:
the lookdev shader/sequence self-check, a tiny scene (screen material + bloom + camera-ray world +
3-light rig + cyc), apply_look twice, save_blend, two stills with a mask through stills.main, a mask
rendered with the look's view gamma at 1.2 (the class counts must match gamma 1), and a model-vs-mask
width. Then asserts the written JSON: decoded sequence frames, glossy flags, bloom group, world nodes,
grade nodes, stills.json fields, band maths, bake channels, the gamma-pinned mask. Exit 1 on any failure
or when Blender is missing. Renders stay tiny (160x90, 8 samples). Output folder: the system temp
(kept on failure, printed).
"""
import sys
sys.dont_write_bytecode = True
import json
import os
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.normpath(os.path.join(HERE, ".."))
BLENDER = os.environ.get("BLENDER") or "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


def main():
    if not os.path.exists(BLENDER):
        print(f"FAIL: Blender not found at {BLENDER} (set env BLENDER)")
        return 1
    out = tempfile.mkdtemp(prefix="film_look_check_")
    cmd = [BLENDER, "-b", "--factory-startup", "-P", os.path.join(ENGINE, "filmkit", "blender", "gpu.py"),
           "-P", os.path.join(HERE, "look_scene_blender.py"), "--", "--out", out]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=900)
    log = proc.stdout + proc.stderr
    with open(os.path.join(out, "blender.log"), "w", encoding="utf-8") as fh:
        fh.write(log)
    gpu_line = next((l for l in log.splitlines() if l.startswith("gpu.py:")), None)
    check(gpu_line is not None, "gpu.py printed no device line")
    check("LOOK SCENE OK" in log, f"Blender run failed (exit {proc.returncode}); see {out}/blender.log")
    for l in log.splitlines():
        if l.startswith(("CHECK ", "STILL", "gpu.py:")):
            print(l)
    if problems:
        tail = "\n".join(log.splitlines()[-25:])
        print(tail)
        print("FAIL: " + "; ".join(problems))
        return 1

    with open(os.path.join(out, "report.json"), encoding="utf-8") as fh:
        rep = json.load(fh)
    with open(os.path.join(out, "stills", "stills.json"), encoding="utf-8") as fh:
        st = json.load(fh)
    sc = rep["selfcheck"]
    check(sc["ok"] is True, f"selfcheck: {sc.get('problems')}")
    for f in (1, 2, 3):
        check(sc[f"frame_{f}"]["seq_shows"] == f, f"selfcheck frame {f} shows {sc[f'frame_{f}']['seq_shows']}")
    check(sc["frame_2"]["keyed"] > 2.5 and sc["frame_3"]["keyed"] < 0.05, f"keyed props: {sc['frame_2']}, {sc['frame_3']}")
    check(all(abs(sc[f"frame_{f}"]["noprops"] - 1.0) < 0.05 for f in (1, 2, 3)), "no-props plane not 1.0")
    for n, want in (("key", True), ("rim", False), ("fill", False)):
        check(rep["lights"][n]["glossy"] is want and rep["lights"][n]["camera"] is False, f"light {n} flags {rep['lights'][n]}")
        check(rep["lights"][n]["parent"] == "light_rig", f"light {n} not on the rig")
    check(rep["lights"]["key"]["watts"] == 60.0, f"key watts {rep['lights']['key']['watts']}")
    check(rep["rig_follow"] == "hero", "light rig does not follow the hero root")
    b = rep["bloom"]
    check(b["group"] == "film_bloom" and b["use_compositing"] and b["use_pass_emit"] and b["type"] == "Bloom", f"bloom {b}")
    check({"Background", "camera_bg", "camera_ray", "camera_mix"} <= set(rep["world"]["nodes"]), f"world nodes {rep['world']['nodes']}")
    g = rep["grade"]
    check(g["screen_has_grade"] and g["card_has_grade"] and g["screen_glow_hi"] and g["card_grade_removed"], f"grade nodes {g}")
    check(rep["idempotent"]["materials_same_nodes"] and rep["idempotent"]["objects_same"], f"apply_look not idempotent {rep['idempotent']}")
    check(rep["stored_look"] == "D97757", "look not stored on the scene")
    check(abs(rep["cyc_min_z"] + 0.5) < 1e-5, f"cyc floor {rep['cyc_min_z']}")
    rt = rep["rig_track"]
    check(rt["n"] == 3 and abs(rt["rz"][0]) < 0.2 and abs(rt["rz"][1]) < 0.2 and 0.6 <= min(rt["gain"]) <= max(rt["gain"]) <= 1.6, f"rig track {rt}")
    bands = rep["bands"]
    check(tuple(bands["front"]) == ("B", 245, 256), f"front band {bands['front']}")
    check(bands["top"][1] <= 231 < bands["top"][2] and bands["top"][2] <= bands["front"][1], f"top band {bands['top']}")
    check(bands["parts"][1] <= 108 < bands["parts"][2] < bands["bevel"][1], f"parts band {bands['parts']}")
    check(bands["body"][0] == "B" and bands["body"][1] <= 108 and bands["body"][2] == 256, f"body band {bands['body']}")
    check(bands["studio"][0] == "G" and bands["studio"][1] <= 188 < bands["studio"][2], f"studio band {bands['studio']}")
    ch = rep["channels"]
    check(ch["n"] == 2 * 17 and ch["scale_clamped"] and ch["hide_const"] == [[1, 0.0, 0], [2, 1.0, 0]], f"channels {ch}")
    check(rep["save"]["non_relative"] == [] and rep["save"]["objects"] >= 10, f"save {rep['save']}")
    check(rep["blend_mtime_after"] == os.path.getmtime(os.path.join(out, "chk.blend")), "stills changed the .blend")

    check([e["frame"] for e in st] == [1, 12], f"stills.json frames {[e['frame'] for e in st]}")
    for e in st:
        for k in ("frame", "t", "seconds_render", "colour", "silhouette", "hot", "void", "studio_luma", "max", "content_in_frame"):
            check(k in e, f"stills.json f{e['frame']} misses {k}")
        check(e["seconds_render"] > 0 and os.path.exists(e["path"]) and os.path.exists(e["mask_path"]), f"f{e['frame']} files")
        col = e["colour"]
        check("front" in col and col["front"]["n"] > 30 and "err" in col["front"], f"f{e['frame']} front class {col.get('front')}")
        check("body" in col and col["body"]["n"] > col["front"]["n"], f"f{e['frame']} body class {col.get('body')}")
        check("parts" in col and col["parts"]["n"] > 10, f"f{e['frame']} parts class {col.get('parts')}")
        check("studio" in col and e["void"] is not None and 0 < e["void"]["all"] < 1, f"f{e['frame']} studio/void {col.get('studio')} {e['void']}")
        sil = e["silhouette"]
        check(sil["mask_w"] is not None and 0.1 < sil["mask_w"] < 0.9 and 0.05 < sil["mask_h"] < 0.9, f"f{e['frame']} silhouette {sil}")
        check(isinstance(e["hot"]["n"], int), f"f{e['frame']} hot {e['hot']}")
    c1, c12 = st[0]["colour"], st[1]["colour"]
    check("seq_f1" in c1 and "seq_f12" not in c1, f"frame 1 screen shows {sorted(k for k in c1 if k.startswith('seq'))}")
    check("seq_f12" in c12 and "seq_f1" not in c12, f"frame 12 screen shows {sorted(k for k in c12 if k.startswith('seq'))}")
    pts = rep["points"]
    check(pts["model_w"] is not None and abs(pts["model_w"] - pts["mask_w"]) < 0.03, f"model_w {pts['model_w']} vs mask_w {pts['mask_w']}")
    ms = rep["mask_skip"]
    check(ms["with_skip"] > 10 and ms["with_skip"] >= 1.5 * ms["without_skip"] and ms["camera_visible_restored"] is True,
          f"mask_skip honoured (arm class px with the occluder skipped vs not): {ms}")
    mg = rep["mask_gamma"]
    check(mg["parts"] >= 10 and abs(mg["parts"] - ms["with_skip"]) <= max(2, 0.05 * ms["with_skip"])
          and abs(mg["gamma_restored"] - 1.2) < 1e-6,
          f"the mask render pins the view gamma at 1 (parts {mg['parts']} px at look gamma 1.2 vs {ms['with_skip']} at 1) "
          f"and restores the look's gamma ({mg['gamma_restored']})")
    pc = rep["points_cli"]
    check(pc["model_w"] is not None and abs(pc["model_w"] - pc["mask_w"]) < 0.03, f"--points CLI fills model_w: {pc}")
    pyc = [os.path.join(d, n) for d, _, ns in os.walk(ENGINE) for n in ns if n.endswith(".pyc")]
    check(not pyc, f"bytecode left in the engine: {pyc[:3]}")

    if problems:
        print(f"FAIL ({len(problems)}): " + " | ".join(problems))
        print(f"outputs kept in {out}")
        return 1
    print(f"blender look: selfcheck ok, 3 lights, bloom, world, 2 stills with mask; model_w {pts['model_w']} mask_w {pts['mask_w']}; "
          f"mask_skip parts {ms['with_skip']} vs {ms['without_skip']} px; --points model_w {pc['model_w']}; {gpu_line}")
    shutil.rmtree(out, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
