import os
from PIL import Image

def resize_and_save(src_path, dest_path, size):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    img = Image.open(src_path)
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    resized.save(dest_path, "PNG")

def copy_splash(src_path, dest_path, width, height):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    # Open base standard icon
    icon = Image.open("static/icons/icon-512.png")
    # Resize icon to fit nicely in splash (e.g. 1/4 of shortest dimension)
    icon_size = min(width, height) // 4
    icon_resized = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    
    # Create solid background image
    splash = Image.new("RGBA", (width, height), (15, 23, 42, 255))
    
    # Center paste
    offset_x = (width - icon_size) // 2
    offset_y = (height - icon_size) // 2
    splash.paste(icon_resized, (offset_x, offset_y), icon_resized)
    splash.save(dest_path, "PNG")

def main():
    res_path = "mobile/android/app/src/main/res"
    icon_src = "static/icons/icon-512.png"
    
    # Android mipmap launcher icon sizes
    mipmap_sizes = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192
    }
    
    print("Generating launcher icons...")
    for folder, size in mipmap_sizes.items():
        # Override standard launcher icons
        resize_and_save(icon_src, os.path.join(res_path, folder, "ic_launcher.png"), size)
        resize_and_save(icon_src, os.path.join(res_path, folder, "ic_launcher_round.png"), size)
        resize_and_save(icon_src, os.path.join(res_path, folder, "ic_launcher_foreground.png"), size)
        print(f"Saved icons for {folder} ({size}x{size})")
        
    print("Generating splash screens...")
    # Portraits
    portraits = {
        "drawable": (512, 512), # default fallback
        "drawable-port-hdpi": (480, 800),
        "drawable-port-mdpi": (320, 480),
        "drawable-port-xhdpi": (720, 1280),
        "drawable-port-xxhdpi": (960, 1600),
        "drawable-port-xxxhdpi": (1280, 1920)
    }
    
    for folder, (w, h) in portraits.items():
        copy_splash(icon_src, os.path.join(res_path, folder, "splash.png"), w, h)
        print(f"Saved portrait splash to {folder} ({w}x{h})")
        
    # Landscapes
    landscapes = {
        "drawable-land-hdpi": (800, 480),
        "drawable-land-mdpi": (480, 320),
        "drawable-land-xhdpi": (1280, 720),
        "drawable-land-xxhdpi": (1600, 960),
        "drawable-land-xxxhdpi": (1920, 1280)
    }
    
    for folder, (w, h) in landscapes.items():
        copy_splash(icon_src, os.path.join(res_path, folder, "splash.png"), w, h)
        print(f"Saved landscape splash to {folder} ({w}x{h})")

if __name__ == "__main__":
    main()
