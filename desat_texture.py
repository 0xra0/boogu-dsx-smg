"""Histogram-match a texture's SATURATION onto a reference texture's.

`relevel_texture.py` matched the luma CDF onto body_d and deliberately preserved
chroma.  For the scope that was the wrong call: measured on the shipped set,

    texture        S p99    pixels sat>0.45
    mag_d          0.130    0.03 %
    muzzle_d       0.042    0.18 %
    body_d         0.257    0.52 %
    scope_d        0.625    1.56 %     <- 2.4x the body, 5x the magazine

Those are the lime-green, pink and olive blotches Trellis2 baked into the scope
albedo, and they are what made the optic look "weird" on a model whose geometry
is actually clean.  Same fix as the luma, one channel over: map the source's
saturation through the reference's CDF.  Hue and value are untouched, so every
panel line, scratch and wear mark survives - only the colour noise goes.

Usage: python3 desat_texture.py SRC.png REF.png OUT.png
"""
import sys
import numpy as np
from PIL import Image

SRC, REF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]


def to_hsv(rgb):
    mx = rgb.max(2)
    mn = rgb.min(2)
    d = mx - mn
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    return mx, s, d


def stats(tag, rgb):
    _, s, _ = to_hsv(rgb)
    print(f"  {tag:10} S mean={s.mean():.4f} p99={np.percentile(s, 99):.4f} "
          f"sat>0.45={100 * (s > 0.45).mean():.2f}%")


src = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32) / 255.0
ref = np.asarray(Image.open(REF).convert("RGB")).astype(np.float32) / 255.0
print("before")
stats("source", src)
stats("reference", ref)

v, s, _ = to_hsv(src)
_, sref, _ = to_hsv(ref)

# CDF match, 512 bins over [0,1]
bins = 512
hs, edges = np.histogram(s.ravel(), bins=bins, range=(0, 1))
hr, _ = np.histogram(sref.ravel(), bins=bins, range=(0, 1))
cs = np.cumsum(hs).astype(np.float64)
cr = np.cumsum(hr).astype(np.float64)
cs /= cs[-1]
cr /= cr[-1]
centres = (edges[:-1] + edges[1:]) / 2
lut = np.interp(cs, cr, centres)          # source bin -> reference saturation
idx = np.clip((s * bins).astype(np.int32), 0, bins - 1)
s_new = lut[idx].astype(np.float32)

# Rebuild RGB keeping hue and value: for a pixel with value v and saturation s,
# min channel = v*(1-s).  Rescaling the gap between each channel and the max by
# the new saturation preserves hue exactly.
gap = v[..., None] - src                  # >= 0, zero on the max channel
old = (v * s)[..., None]
new = (v * s_new)[..., None]
scale = np.divide(new, old, out=np.ones_like(old), where=old > 1e-6)
out = v[..., None] - gap * scale
out = np.clip(out, 0.0, 1.0)

print("after")
stats("output", out)
Image.fromarray((out * 255.0 + 0.5).astype(np.uint8)).save(OUT)
print("wrote", OUT)
