# Brain animation theme integration

The source `assets/neuro-code.webp` is retained byte-for-byte. The README
selects transparent light/dark derivatives with GitHub's supported `picture`
markup. Full transparency at the canvas boundary exposes the actual page
background, including dimmed and high-contrast themes; no page colour is
baked into either asset.

Both derivatives retain 1200 × 480 spatial coordinates, 475 frames, every
source frame duration, the 39,583 ms cycle and infinite looping. There is no
crop, resize, frame interpolation, regenerated anatomy, or change of motion.

The dark derivative removes the black matte with soft alpha and compensates
edge RGB. The light derivative maps the same source hue and intensity to
translucent coloured ink. This changes contrast for a light background.
The original is already lossy; these derivatives are also lossy. Pixelwise
colour identity and a recoverable original alpha channel are not claimed.

Reproduce with Python, Pillow 12.3.0 and NumPy 2.3.5:

```sh
python tools/render_brain_transparency.py
```

The renderer verifies source SHA-256, frame count, dimensions, each frame's
duration, looping, transparent canvas edges, and transparency wherever the
source was exactly black. It writes `assets/neuro-code-transparency.json`.
The dark report also measures the error after compositing back onto black.
This metric measures conversion fidelity, not visual accessibility.

Only the hero image markup is changed. The source image, profile text,
research atlas and other visual assets remain as they were.

Reference: https://github.blog/changelog/2022-08-15-specify-theme-context-for-images-in-markdown-ga/
