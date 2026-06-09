import os
from PIL import Image, ImageDraw

def create_desktop_screenshot(dest_path):
    w, h = 1280, 800
    img = Image.new("RGBA", (w, h), (15, 23, 42, 255)) # Slate 900 background
    draw = ImageDraw.Draw(img)
    
    # 1. Sidebar background (Slate 800)
    draw.rectangle([0, 0, 240, h], fill=(30, 41, 59, 255))
    
    # Brand logo representation in sidebar
    draw.ellipse([20, 20, 50, 50], fill=(139, 92, 246, 255)) # Brand purple
    # Inner 'L'
    draw.line([(31, 28), (31, 42)], fill=(255, 255, 255, 255), width=3)
    draw.line([(31, 42), (40, 42)], fill=(255, 255, 255, 255), width=3)
    
    # Sidebar items
    for idx, label in enumerate(["Dashboard", "Documents", "Workspaces", "Activity", "Insights"]):
        y = 80 + idx * 45
        # Draw small icon placeholders
        draw.rectangle([25, y + 5, 40, y + 20], fill=(100, 116, 139, 255))
        # Draw mock text lines
        draw.rectangle([55, y + 8, 180, y + 16], fill=(100, 116, 139, 255) if idx != 0 else (139, 92, 246, 255))
        
    # User Profile card at sidebar bottom
    draw.rectangle([0, h - 70, 240, h], fill=(15, 23, 42, 255))
    draw.ellipse([15, h - 55, 45, h - 25], fill=(139, 92, 246, 255))
    draw.rectangle([55, h - 48, 180, h - 40], fill=(148, 163, 184, 255))
    draw.rectangle([55, h - 35, 140, h - 29], fill=(100, 116, 139, 255))
    
    # 2. Main content area header bar
    draw.rectangle([240, 0, w, 60], fill=(30, 41, 59, 255))
    draw.rectangle([260, 22, 360, 38], fill=(248, 250, 252, 255)) # Title placeholder
    draw.rounded_rectangle([w - 150, 15, w - 30, 45], fill=(139, 92, 246, 255), radius=6) # Action button placeholder
    
    # 3. Chat Area - Message Mockups
    # User Message (Right-aligned, purple)
    draw.rounded_rectangle([w - 450, 120, w - 50, 180], fill=(124, 58, 237, 255), radius=10)
    draw.rectangle([w - 430, 138, w - 100, 148], fill=(255, 255, 255, 255))
    draw.rectangle([w - 430, 153, w - 200, 163], fill=(255, 255, 255, 255))
    
    # Assistant Message (Left-aligned, slate 800)
    draw.rounded_rectangle([290, 220, 750, 350], fill=(30, 41, 59, 255), radius=10)
    draw.rectangle([310, 240, 710, 250], fill=(148, 163, 184, 255))
    draw.rectangle([310, 260, 680, 270], fill=(148, 163, 184, 255))
    draw.rectangle([310, 280, 720, 290], fill=(148, 163, 184, 255))
    draw.rectangle([310, 300, 500, 310], fill=(148, 163, 184, 255))
    
    # Citations tag representation
    draw.rounded_rectangle([310, 320, 420, 336], fill=(8, 145, 178, 255), radius=4) # Cyan tag
    
    # 4. Input bar bottom representation
    draw.rounded_rectangle([290, h - 90, w - 50, h - 30], fill=(30, 41, 59, 255), radius=12)
    draw.rectangle([310, h - 68, w - 180, h - 52], fill=(100, 116, 139, 255))
    draw.ellipse([w - 85, h - 70, w - 65, h - 50], fill=(139, 92, 246, 255)) # Send button
    
    img.save(dest_path, "PNG")
    print(f"Saved desktop screenshot to {dest_path}")

def create_mobile_screenshot(dest_path):
    w, h = 720, 1280
    img = Image.new("RGBA", (w, h), (15, 23, 42, 255)) # Slate 900 background
    draw = ImageDraw.Draw(img)
    
    # 1. Top bar
    draw.rectangle([0, 0, w, 100], fill=(30, 41, 59, 255))
    # Menu button icon
    draw.line([(30, 40), (60, 40)], fill=(248, 250, 252, 255), width=4)
    draw.line([(30, 50), (60, 50)], fill=(248, 250, 252, 255), width=4)
    draw.line([(30, 60), (60, 60)], fill=(248, 250, 252, 255), width=4)
    # Title
    draw.rectangle([120, 38, 320, 62], fill=(248, 250, 252, 255))
    # Top Action Button
    draw.ellipse([w - 60, 50, w - 30, 50], fill=(148, 163, 184, 255)) # dots
    
    # 2. Chat Area - Message Mockups
    # User message
    draw.rounded_rectangle([w - 550, 160, w - 40, 260], fill=(124, 58, 237, 255), radius=12)
    draw.rectangle([w - 520, 185, w - 80, 205], fill=(255, 255, 255, 255))
    draw.rectangle([w - 520, 215, w - 180, 235], fill=(255, 255, 255, 255))
    
    # Assistant message
    draw.rounded_rectangle([40, 310, w - 100, 580], fill=(30, 41, 59, 255), radius=12)
    draw.rectangle([70, 340, w - 140, 360], fill=(148, 163, 184, 255))
    draw.rectangle([70, 380, w - 170, 400], fill=(148, 163, 184, 255))
    draw.rectangle([70, 420, w - 130, 440], fill=(148, 163, 184, 255))
    draw.rectangle([70, 460, w - 240, 480], fill=(148, 163, 184, 255))
    draw.rectangle([70, 500, w - 160, 520], fill=(148, 163, 184, 255))
    # Citation tag
    draw.rounded_rectangle([70, 540, 240, 560], fill=(8, 145, 178, 255), radius=4)
    
    # 3. Input panel
    draw.rounded_rectangle([30, h - 140, w - 30, h - 40], fill=(30, 41, 59, 255), radius=16)
    draw.rectangle([60, h - 100, w - 140, h - 80], fill=(100, 116, 139, 255))
    draw.ellipse([w - 85, h - 105, w - 55, h - 75], fill=(139, 92, 246, 255))
    
    # 4. Mobile navigation bar (bottom)
    draw.rectangle([0, h - 25, w, h], fill=(15, 23, 42, 255))
    
    img.save(dest_path, "PNG")
    print(f"Saved mobile screenshot to {dest_path}")

def main():
    icons_dir = "static/icons"
    os.makedirs(icons_dir, exist_ok=True)
    
    create_desktop_screenshot(os.path.join(icons_dir, "screenshot-desktop.png"))
    create_mobile_screenshot(os.path.join(icons_dir, "screenshot-mobile.png"))

if __name__ == "__main__":
    main()
