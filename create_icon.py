"""Generates assets/icon.ico for MotionWake during build."""
import os
from PIL import Image, ImageDraw

def create_icon():
    os.makedirs("assets", exist_ok=True)
    sizes = [16, 32,48, 64, 128, 256]
    frames = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        margin = size // 8
        draw.ellipse([margin, margin, size - margin, size - margin], fill=(0, 180, 255, 255))
        inner = size // 3
        draw.ellipse([inner, inner, size - inner, size - inner], fill=(20, 20, 30, 255))
        frames.append(img)

    frames[0].save(
        "assets/icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print("icon.ico aangemaakt in assets/")

if __name__ == "__main__":
    create_icon()
