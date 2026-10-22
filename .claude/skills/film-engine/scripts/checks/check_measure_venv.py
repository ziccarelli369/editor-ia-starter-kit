"""check_measure_venv.py: quick check of filmkit.measure's region maths (measure_arrays, erode_mask,
band_region) on synthetic arrays. Needs numpy (kit venv); no ffmpeg, no files.

Fixture: a 240x320 beauty and class mask. A bright 'screen' class (mask G 200, beauty 255) sits top
left over a black world; to its right its motion blur ramps G 200 -> 0 over 60 px, so the ramp crosses
the studio band (G 113..133) in a 6 px ring that no class owns, luma about 150.
(A) No real studio in frame: a 2 px erosion keeps the ring (a false studio entry, bright median, a
studio_luma); the 8 px guard drops it (no entry, studio_luma None).
(B) The bottom half is real studio (luma 30): the guard keeps every studio pixel further than 8 px
from the band's edge, the frame border included (no wrap-around: (120 - 8) * 320 pixels), median 30.
Also: erode_mask pads with the edge value; band_region takes a channel letter or index; hot pixels
count the screen and the bright end of the ramp.

  <kit venv python> -B check_measure_venv.py
"""
import sys
sys.dont_write_bytecode = True
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import numpy as np  # noqa: E402
from filmkit import measure  # noqa: E402

H, W = 240, 320
BANDS = {"screen": ("G", 190, 210), "studio": ("G", 113, 133), "body": ("B", 100, 256)}


def fixture(real_studio):
    img, msk = np.zeros((H, W, 3)), np.zeros((H, W, 3))
    img[20:80, 40:200] = 255.0
    msk[20:80, 40:200, 1] = 200.0
    a = np.linspace(1.0, 0.0, 60, endpoint=False)                 # the blur ramp, screen share 1 -> 0
    img[20:80, 200:260] = 255.0 * a[None, :, None]
    msk[20:80, 200:260, 1] = 200.0 * a[None, :]
    if real_studio:
        img[120:, :] = 30.0
        msk[120:, :, 1] = 123.0
    return img, msk


def main():
    failures = []

    def check(cond, text):
        print(("ok   " if cond else "FAIL ") + text)
        if not cond:
            failures.append(text)

    img, msk = fixture(False)
    ring = measure.band_region(msk, BANDS["studio"])
    check(int(ring.sum()) == 360, f"the blur ramp leaves a {int(ring.sum())} px ring inside the studio band (6 x 60)")
    r0 = measure.measure_arrays(img, msk, BANDS, studio_guard=0)
    st0 = r0["colour"].get("studio")
    check(st0 is not None and st0["n"] == 112 and st0["median"][0] > 100 and r0["studio_luma"] > 100,
          f"guard 0 (erode 2 alone): a false studio entry {st0}, studio_luma {r0['studio_luma']}")
    r8 = measure.measure_arrays(img, msk, BANDS, studio_guard=8)
    check("studio" not in r8["colour"] and r8["studio_luma"] is None,
          f"guard 8: no studio entry ({r8['colour'].get('studio')}), studio_luma {r8['studio_luma']}")
    check(r8["colour"]["screen"]["n"] == (60 - 4) * (160 - 4) + 0 or r8["colour"]["screen"]["n"] > 8000,
          f"the screen class is unaffected by the guard: n {r8['colour']['screen']['n']}")
    check(r8["hot"]["n"] == 160 * 60 + 3 * 60 and r8["hot"]["max_outside"] == 255.0, f"hot pixels: {r8['hot']}")
    check(r8["silhouette"] is None and r8["void"]["all"] == round(360 / (H * W), 4), f"no hero; void from the raw band {r8['void']}")

    img, msk = fixture(True)
    rb = measure.measure_arrays(img, msk, BANDS, studio_guard=8)
    stb = rb["colour"]["studio"]
    check(stb["n"] == (120 - 8) * W and stb["median"] == [30.0, 30.0, 30.0] and rb["studio_luma"] == 30.0,
          f"guard 8 with real studio: n {stb['n']} = (120 - 8) * 320, median {stb['median']}, luma {rb['studio_luma']}")
    check(abs(rb["void"]["all"] - (120 * W + 360) / (H * W)) < 1e-3, f"void.all counts the raw band {rb['void']}")
    rb2 = measure.measure_arrays(img, msk, BANDS, erode=12, studio_guard=8)
    check(rb2["colour"]["studio"]["n"] == (120 - 12) * W, "the studio erosion is max(erode, studio_guard)")

    # a thin class (a 3 px bar, 60 px long) is eroded 1 px, not 2, so it reaches the report (r3-23); the anti-aliased
    # ramp of a neighbouring level (1 px wide, 200 raw px) that falls into its band vanishes under that 1 px; a wide
    # class keeps the full 2 px erosion (bit-identical counts)
    img3, msk3 = fixture(True)
    bands3 = dict(BANDS, bar=("B", 60, 80))
    msk3[150:153, 30:90, 2] = 70.0                       # the bar: 3 x 60 px
    img3[150:153, 30:90] = (10.0, 20.0, 30.0)
    msk3[200, 20:220, 2] = 70.0                          # a 1 px ramp line in the same band, 200 px
    r3 = measure.measure_arrays(img3, msk3, bands3, studio_guard=8)
    bar = r3["colour"].get("bar")
    check(bar is not None and bar["n"] == 58 and bar["median"] == [10.0, 20.0, 30.0],
          f"thin class: 3 x 60 px bar eroded 1 px -> {bar} (2 px would leave 0)")
    r3off = measure.measure_arrays(img3, msk3, bands3, studio_guard=8, thin_px=0)
    check("bar" not in r3off["colour"], f"thin_px 0: the bar is eroded 2 px and dropped ({r3off['colour'].get('bar')})")
    check(r3["colour"]["studio"]["n"] == rb["colour"]["studio"]["n"] and r3["colour"]["screen"]["n"] == rb["colour"]["screen"]["n"],
          "wide classes keep the full erosion under the thin rule")
    wide = np.zeros((H, W), bool)
    wide[100:140, 100:140] = True                        # 40 x 40: 1444 px after 1 px >= 200 -> full erosion
    check(measure.class_erosion(wide, 2, 200) == 2 and measure.class_erosion(msk3[..., 2] == 70.0, 2, 200) == 1
          and measure.class_erosion(wide, 2, 0) == 2 and measure.class_erosion(wide, 1, 200) == 1,
          "class_erosion: wide -> erode, thin -> 1, off -> erode, erode 1 -> 1")

    m = np.ones((5, 5), bool)
    m[2, 2] = False
    e = measure.erode_mask(m, 1)
    check(int(e.sum()) == 20 and e[0].all() and e[:, 0].all(), "erode_mask: the border keeps its edge value, the hole grows by 1")
    check(np.array_equal(measure.band_region(msk, ("G", 113, 133)), measure.band_region(msk, (1, 113, 133))),
          "band_region: channel letter and index agree")
    print(f"measure check: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
