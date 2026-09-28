"""Compare two images and print numeric differences.
Outputs JSON with: mse, mae, mean_per_channel_diff, max_diff, percent_pixels_gt_0.01
"""
from PIL import Image
import numpy as np
import sys
import json

def compare(a_path, b_path):
    a = Image.open(a_path).convert('RGBA')
    b = Image.open(b_path).convert('RGBA')
    if a.size != b.size:
        raise SystemExit(f"DIFFERENT_SIZE {a.size} vs {b.size}")
    A = np.array(a).astype(np.float32) / 255.0
    B = np.array(b).astype(np.float32) / 255.0
    diff = A - B
    absdiff = np.abs(diff)
    mse = float(np.mean((diff ** 2)))
    mae = float(np.mean(absdiff))
    mean_per_channel = list(map(float, np.mean(absdiff, axis=(0,1))))
    max_diff = float(np.max(absdiff))
    # percent of pixels where luminance diff > 0.01
    lumA = 0.2126*A[:,:,0] + 0.7152*A[:,:,1] + 0.0722*A[:,:,2]
    lumB = 0.2126*B[:,:,0] + 0.7152*B[:,:,1] + 0.0722*B[:,:,2]
    lumdiff = np.abs(lumA - lumB)
    pct_gt_001 = float(np.mean(lumdiff > 0.01))
    return {
        'a': a_path,
        'b': b_path,
        'mse': mse,
        'mae': mae,
        'mean_per_channel_absdiff': mean_per_channel,
        'max_absdiff': max_diff,
        'pct_pixels_lum_gt_0.01': pct_gt_001
    }

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: compare_images.py a.png b.png')
        sys.exit(2)
    out = compare(sys.argv[1], sys.argv[2])
    print(json.dumps(out, indent=2))
