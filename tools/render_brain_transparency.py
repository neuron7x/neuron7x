"""Generate theme-aware derivatives of the immutable brain animation.

Run from any directory with Pillow==12.3.0 and numpy==2.3.5.
Uses Pillow's streaming libwebp encoder to avoid retaining 475 RGBA frames.
No spatial resampling, frame dropping, retiming, or generated imagery.
Dark: remove the black matte and unpremultiply soft edge colours.
Light: retain source hue while mapping emitted light to translucent ink.
Alpha quantization limits download size. Encoding is lossy; the original
asset is retained byte-for-byte, and colour identity is not claimed.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image, _webp

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/neuro-code.webp'
SOURCE_SHA256 = '9e15867042ec6c8f51746a255410a3417b295517d3cb698511895207c1004f8e'


def convert(frame, theme):
    rgb = np.asarray(frame.convert('RGB'), dtype=np.float32)
    peak = rgb.max(axis=2)
    if theme == 'dark':
        alpha = np.minimum(255, peak * 255 / 32)
        alpha[peak <= 2] = 0
        alpha = np.rint(alpha / 17) * 17
        foreground = np.minimum(255, rgb * 255 / np.maximum(alpha[..., None], 1))
    else:
        alpha = np.minimum(1, (np.maximum(peak - 3, 0) / 100) ** 0.8) * 255
        alpha = np.rint(alpha * 31 / 255) * 255 / 31
        foreground = rgb / np.maximum(peak[..., None], 1) * 100
    # Decoder noise at canvas boundaries must never create a visible seam.
    alpha[0, :] = alpha[-1, :] = alpha[:, 0] = alpha[:, -1] = 0
    rgba = np.rint(np.dstack((foreground, alpha))).clip(0, 255).astype(np.uint8)
    return Image.fromarray(rgba)


def render(theme):
    source = Image.open(SOURCE)
    output_path = ROOT / f'assets/neuro-code-{theme}.webp'
    encoder = _webp.WebPAnimEncoder(source.size, 0, source.info.get('loop', 0), False, 3, 5, False, False)
    timestamp = 0
    for index in range(source.n_frames):
        source.seek(index)
        source.load()
        frame = convert(source, theme)
        encoder.add(frame.getim(), timestamp, False, 80, 70, 3)
        timestamp += source.info['duration']
        if index % 100 == 0:
            print(f'{theme}: {index}/{source.n_frames}', flush=True)
    encoder.add(None, timestamp, False, 80, 70, 0)
    output_path.write_bytes(encoder.assemble('', '', ''))
    output = Image.open(output_path)
    assert output.n_frames == source.n_frames
    assert output.size == source.size
    assert output.info['loop'] == source.info['loop']
    edge_alpha = 0
    max_error = 0
    squared_error = 0.0
    samples = 0
    for index in range(source.n_frames):
        source.seek(index); source.load()
        output.seek(index); output.load()
        assert output.info['duration'] == source.info['duration']
        actual = np.asarray(output.convert('RGBA'), dtype=np.float32)
        original = np.asarray(source.convert('RGB'), dtype=np.float32)
        alpha = actual[..., 3]
        edge_alpha = max(edge_alpha, int(max(alpha[0].max(), alpha[-1].max(), alpha[:, 0].max(), alpha[:, -1].max())))
        assert np.all(alpha[original.max(axis=2) == 0] == 0)
        if theme == 'dark':
            delta = np.rint(actual[..., :3] * alpha[..., None] / 255) - original
            max_error = max(max_error, int(np.abs(delta).max()))
            squared_error += float(np.square(delta).sum())
            samples += delta.size
    assert edge_alpha == 0
    report = dict(theme=theme, source_sha256=SOURCE_SHA256, output_sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(), frames=output.n_frames, dimensions=output.size, duration_ms=timestamp, all_frame_durations_equal=True, loop=output.info['loop'], outer_edge_alpha_max=edge_alpha, original_black_pixels_transparent=True, output_bytes=output_path.stat().st_size)
    if theme == 'dark':
        report.update(black_composite_max_channel_error=max_error, black_composite_rmse=(squared_error/samples)**0.5)
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(render, ['dark', 'light']))
    (ROOT / 'assets/neuro-code-transparency.json').write_text(json.dumps(reports, indent=2) + '\n')
