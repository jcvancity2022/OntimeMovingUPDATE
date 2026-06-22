"""Generate responsive image variants for homepage images.

Usage:
    python tools/resize_images.py --src images/homepage --out images/homepage/variants

This script requires Pillow (pip install Pillow).
It will convert PNGs to JPEG and WebP variants at widths: 320, 640, 1024, 1600.
"""
import argparse
from pathlib import Path
from PIL import Image

WIDTHS = [320, 640, 1024, 1600]
JPEG_QUALITY = 80

EXT_OUT = ['jpg', 'webp']


def make_variants(src_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    for img_path in sorted(src_dir.glob('*.png')):
        with Image.open(img_path) as im:
            im = im.convert('RGB')
            for w in WIDTHS:
                ratio = w / im.width
                h = max(1, int(im.height * ratio))
                resized = im.resize((w, h), Image.LANCZOS)
                for ext in EXT_OUT:
                    out_name = f"{img_path.stem}-w{w}.{ext}"
                    out_file = out_dir / out_name
                    if ext == 'jpg':
                        resized.save(out_file, 'JPEG', quality=JPEG_QUALITY, optimize=True)
                    else:
                        # webp
                        resized.save(out_file, 'WEBP', quality=80, method=6)
                    print(f"Wrote: {out_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', type=Path, default=Path('images/homepage'), help='Source images folder')
    parser.add_argument('--out', type=Path, default=Path('images/homepage'), help='Output folder for variants')
    args = parser.parse_args()
    make_variants(args.src, args.out)
