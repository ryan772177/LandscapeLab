from PIL import Image
import numpy as np
import sys

def load_rgba(path):
    im = Image.open(path).convert('RGBA')
    return im

def make_heatmap(diff):
    # diff: float array 0..1
    d = np.clip(diff, 0.0, 1.0)
    # simple red-yellow colormap
    r = np.clip(2.0 * d, 0, 1)
    g = np.clip(2.0 * (1.0 - np.abs(d - 0.5) * 2.0), 0, 1)
    b = np.clip(2.0 * (1.0 - d), 0, 1)
    heat = np.stack([r, g, b], axis=2)
    heat = (heat * 255).astype(np.uint8)
    return Image.fromarray(heat)


def main(a_path, b_path, out_path):
    a = load_rgba(a_path)
    b = load_rgba(b_path)

    # REFUSE a size mismatch; never repair one. This resampled B onto A's
    # size with LANCZOS until 2026-08-08 and then reported the difference
    # as though the frames were comparable. A resample INVENTS pixels, so
    # every statistic below would carry resampling error mixed into the
    # quantity being measured, with nothing in the output saying so -- and
    # the capture noise floor between two identical-settings runs is
    # already 1.2-3.5% mean|diff| (measured 2026-08-06), which a resample
    # can exceed on its own. That turns "I couldn't look" into a number,
    # which non-negotiable 6 forbids.
    #
    # Same precondition, same message and same exit code as
    # scripts/compare_images.py. THE TWO ARE STILL WRITTEN TWICE, which is
    # non-negotiable 24; BACKLOG B-IMAGE-PAIR folds them into one shared
    # load_comparable_pair(). LESSONS 2026-08-08.
    if a.size != b.size:
        raise SystemExit(f"DIFFERENT_SIZE {a.size} vs {b.size}")

    a_arr = np.asarray(a).astype(np.float32) / 255.0
    b_arr = np.asarray(b).astype(np.float32) / 255.0

    # luminance difference
    lum_a = 0.2126 * a_arr[...,0] + 0.7152 * a_arr[...,1] + 0.0722 * a_arr[...,2]
    lum_b = 0.2126 * b_arr[...,0] + 0.7152 * b_arr[...,1] + 0.0722 * b_arr[...,2]
    lum_diff = np.abs(lum_a - lum_b)

    # normalized diff for heatmap
    diff_rgb = np.abs(a_arr[...,:3] - b_arr[...,:3])
    diff_max = diff_rgb.max()
    norm = diff_rgb.mean(axis=2)
    if diff_max > 0:
        norm = norm / diff_max
    heat = make_heatmap(norm)

    # create side-by-side: [A | heat | B]
    spacer = 8
    w, h = a.size
    out_w = w * 3 + spacer * 2
    out_h = h

    out = Image.new('RGBA', (out_w, out_h), (0,0,0,255))
    out.paste(a, (0,0))
    out.paste(heat.convert('RGBA'), (w + spacer, 0))
    out.paste(b, (2*w + spacer*2, 0))

    # draw small overlay text? Keep minimal to avoid dependency on fonts
    out.save(out_path)
    print(out_path)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: python scripts/visual_diff.py <imgA> <imgB> <out>')
        sys.exit(2)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
