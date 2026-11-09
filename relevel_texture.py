"""Match a part's albedo tonal range to the body's, so every part of the weapon
reads as the same material under the same light.

WHY (measured 2026-07-30, from in-game screenshots):

    body_d     mean 88.1   median 83.7    0.1% of pixels below luma 40
    muzzle_d   mean 90.2   median 84.9    0.0%
    mag_d      mean 50.0   median 43.4   44.9%
    scope_d    mean 40.3   median 34.0   65.0%

Trellis2 bakes lighting into the albedo, and it baked the magazine and the scope
far darker than the body.  In game the body looks right - light grey with orange
accents - while the magazine and scope read as near-black lumps stuck onto it.
That is a texture problem, not a geometry or material one, and it is most of why
those two parts looked wrong in every screenshot.

Histogram-match the luminance CDF onto the reference and carry the original
chroma through unchanged, so panel lines, greebles and the orange accents all
survive - this lifts the blacks rather than flattening the map to a solid colour.

Usage:  python3 relevel_texture.py REFERENCE.png TARGET.png [TARGET.png ...]
"""
import os
import shutil
import sys

import numpy as np
from PIL import Image

LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float64)


def luminance(a):
    return a.astype(np.float64) @ LUMA


def cdf(vals):
    h = np.bincount(np.clip(vals, 0, 255).astype(np.uint8).ravel(), minlength=256)
    c = np.cumsum(h).astype(np.float64)
    return c / c[-1]


def main():
    ref_path, targets = sys.argv[1], sys.argv[2:]
    ref = np.asarray(Image.open(ref_path).convert("RGB"))
    ref_cdf = cdf(luminance(ref))

    for t in targets:
        img = Image.open(t).convert("RGB")
        a = np.asarray(img)
        lum = luminance(a)
        src_cdf = cdf(lum)

        # map each source luma level to the level with the nearest reference CDF
        lut = np.interp(src_cdf, ref_cdf, np.arange(256)).astype(np.float64)
        old = np.clip(lum, 0, 255)
        new = lut[old.astype(np.uint8)]

        # scale RGB by the luminance ratio so hue and saturation are preserved
        scale = np.divide(new, np.maximum(old, 1e-6),
                          out=np.ones_like(new), where=old > 1.0)
        out = np.clip(a.astype(np.float64) * scale[..., None], 0, 255).astype(np.uint8)

        bak = t + ".orig"
        if not os.path.exists(bak):
            shutil.copy2(t, bak)
        Image.fromarray(out).save(t)

        nl = luminance(out)
        print(f"  {os.path.basename(t):14} mean {lum.mean():5.1f} -> {nl.mean():5.1f}   "
              f"below-40 {(lum < 40).mean() * 100:5.1f}% -> {(nl < 40).mean() * 100:4.1f}%   "
              f"(original kept at {os.path.basename(bak)})")


if __name__ == "__main__":
    sys.exit(main())
