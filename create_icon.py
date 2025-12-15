"""Script to create application icon with SG letters.

This script creates a simple icon with "SG" letters in the app accent color
on a black background using Pillow.
"""

import io
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Required package not installed. Installing...")
    os.system(f"{sys.executable} -m pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont


def create_sg_icon():
    """Create ICO file with SG letters design."""
    # Paths
    script_dir = Path(__file__).parent
    ico_path = script_dir / "assets" / "icon" / "app.ico"
    
    # Create directories if they don't exist
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Colors from theme
    accent_color = (0, 120, 212, 255)  # #0078d4 - same as button border
    bg_color = (0, 0, 0, 255)  # Black background
    
    # Sizes for ICO file
    sizes = [16, 32, 48, 64, 256]
    images = []
    
    print(f"Creating SG icon: {ico_path}")
    
    for size in sizes:
        print(f"  Generating {size}x{size}...")
        try:
            # Create image with black background
            img = Image.new('RGBA', (size, size), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Calculate scale factor and font size
            scale = size / 256.0
            font_size = max(8, int(180 * scale))  # Proportional font size
            
            # Try to use a bold font, fallback to default if not available
            try:
                # Try system fonts (Windows)
                if sys.platform == "win32":
                    font_paths = [
                        "C:/Windows/Fonts/arialbd.ttf",  # Arial Bold
                        "C:/Windows/Fonts/calibrib.ttf",  # Calibri Bold
                        "C:/Windows/Fonts/segoeuib.ttf",  # Segoe UI Bold
                    ]
                    font = None
                    for font_path in font_paths:
                        if os.path.exists(font_path):
                            try:
                                font = ImageFont.truetype(font_path, font_size)
                                break
                            except:
                                continue
                    if font is None:
                        font = ImageFont.load_default()
                else:
                    # Linux/Mac - try common fonts
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Draw "SG" text
            text = "SG"
            
            # Calculate text position (centered)
            # Get text bounding box
            if hasattr(draw, 'textbbox'):
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            else:
                # Fallback for older PIL
                bbox = draw.textsize(text, font=font)
                text_width, text_height = bbox
            
            x = (size - text_width) // 2
            y = (size - text_height) // 2 - int(10 * scale)  # Slightly move up for better centering
            
            # Draw text with accent color
            draw.text((x, y), text, fill=accent_color, font=font)
            
            # For very small sizes (16x16), make it simpler
            if size <= 16:
                # Redraw with default font for clarity
                img = Image.new('RGBA', (size, size), bg_color)
                draw = ImageDraw.Draw(img)
                font = ImageFont.load_default()
                if hasattr(draw, 'textbbox'):
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                else:
                    bbox = draw.textsize(text, font=font)
                    text_width, text_height = bbox
                x = (size - text_width) // 2
                y = (size - text_height) // 2
                draw.text((x, y), text, fill=accent_color, font=font)
            
            images.append(img)
        except Exception as e:
            print(f"  Warning: Failed to generate {size}x{size}: {e}")
            import traceback
            traceback.print_exc()
    
    if images:
        # Save as ICO
        images[0].save(
            str(ico_path),
            format='ICO',
            sizes=[(img.width, img.height) for img in images]
        )
        print(f"✓ ICO file created: {ico_path}")
        print(f"  Sizes included: {[f'{img.width}x{img.height}' for img in images]}")
        return True
    else:
        print("✗ Failed to create any icon sizes")
        return False


if __name__ == "__main__":
    create_sg_icon()
