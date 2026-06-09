import os
import math
from PIL import Image, ImageDraw

def create_brand_icon(size, maskable=False):
    # Create image with alpha channel
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # SVG coordinates system is 24x24
    # Bounding circle in SVG is cx=12, cy=12, r=10
    # For maskable icons, we scale down the logo to fit within the 60% safe zone
    scale_factor = 0.75 if maskable else 1.0
    
    cx = size / 2.0
    cy = size / 2.0
    r = (10.0 * size / 24.0) * scale_factor
    
    # 1. Draw Gradient Circle
    # Bounding box of the circle
    x0, y0 = cx - r, cy - r
    x1, y1 = cx + r, cy + r
    
    C1 = (139, 92, 246)  # #8B5CF6
    C2 = (34, 211, 238)  # #22D3EE
    
    for y in range(size):
        for x in range(size):
            # Check if pixel is inside the circle
            dx = x - cx
            dy = y - cy
            if dx*dx + dy*dy <= r*r:
                # Calculate projection along the main diagonal
                # Diagonal goes from (x0, y0) to (x1, y1)
                # Normalized coordinate along the diagonal:
                denom = (x1 - x0) + (y1 - y0)
                if denom > 0:
                    t = ((x - x0) + (y - y0)) / denom
                else:
                    t = 0.5
                t = max(0.0, min(1.0, t))
                
                # Interpolate color
                red = int((1 - t) * C1[0] + t * C2[0])
                green = int((1 - t) * C1[1] + t * C2[1])
                blue = int((1 - t) * C1[2] + t * C2[2])
                
                # Draw pixel
                draw.point((x, y), fill=(red, green, blue, 255))

    # 2. Draw Letter 'L' (white, rounded caps and joint)
    # SVG coordinates: M9 7v10h6
    p0_x = (9.0 / 24.0 * size - cx) * scale_factor + cx
    p0_y = (7.0 / 24.0 * size - cy) * scale_factor + cy
    p1_x = (9.0 / 24.0 * size - cx) * scale_factor + cx
    p1_y = (17.0 / 24.0 * size - cy) * scale_factor + cy
    p2_x = (15.0 / 24.0 * size - cx) * scale_factor + cx
    p2_y = (17.0 / 24.0 * size - cy) * scale_factor + cy
    
    w = (2.2 / 24.0 * size) * scale_factor
    
    # Draw thick lines
    draw.line([(p0_x, p0_y), (p1_x, p1_y)], fill=(255, 255, 255, 255), width=int(round(w)))
    draw.line([(p1_x, p1_y), (p2_x, p2_y)], fill=(255, 255, 255, 255), width=int(round(w)))
    
    # Draw rounded joints and caps
    rad = w / 2.0
    for px, py in [(p0_x, p0_y), (p1_x, p1_y), (p2_x, p2_y)]:
        draw.ellipse([px - rad, py - rad, px + rad, py + rad], fill=(255, 255, 255, 255))
        
    return img

def main():
    icons_dir = "static/icons"
    os.makedirs(icons_dir, exist_ok=True)
    
    # Sizes required for PWA & iOS
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    print("Generating standard icons...")
    for size in sizes:
        img = create_brand_icon(size, maskable=False)
        img.save(os.path.join(icons_dir, f"icon-{size}.png"), "PNG")
        print(f"Saved icon-{size}.png")
        
    # Maskable icon (PWA requirement, has a safe area border)
    print("Generating maskable icon...")
    # For maskable icon, we put the logo inside a solid background matching the theme
    maskable_size = 512
    base_img = create_brand_icon(maskable_size, maskable=True)
    
    # Create solid background image (#0f172a / dark slate)
    bg_img = Image.new("RGBA", (maskable_size, maskable_size), (15, 23, 42, 255))
    # Alpha composite the logo over the solid background
    final_maskable = Image.alpha_composite(bg_img, base_img)
    final_maskable.save(os.path.join(icons_dir, "maskable-icon.png"), "PNG")
    print("Saved maskable-icon.png")
    
    # Generate Splash Screen
    # Android/iOS splash screen (solid dark background with centered icon)
    print("Generating splash screen...")
    splash_w, splash_h = 1080, 1920
    splash = Image.new("RGBA", (splash_w, splash_h), (15, 23, 42, 255))
    
    # Create 256x256 icon to place in center
    center_icon = create_brand_icon(256)
    
    # Paste centered
    offset_x = (splash_w - 256) // 2
    offset_y = (splash_h - 256) // 2
    splash.paste(center_icon, (offset_x, offset_y), center_icon)
    splash.save(os.path.join(icons_dir, "splash.png"), "PNG")
    print("Saved splash.png")

    # Generate Windows Icon (.ico) for desktop app
    print("Generating desktop .ico asset...")
    desktop_assets_dir = "desktop/assets"
    os.makedirs(desktop_assets_dir, exist_ok=True)
    
    ico_img = create_brand_icon(256)
    ico_img.save(os.path.join(desktop_assets_dir, "icon.ico"), format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Saved icon.ico to desktop/assets")

if __name__ == "__main__":
    main()

