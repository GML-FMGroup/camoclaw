# Skill: Python-Based Moodboard Generation with PIL

type: technical

---

## When to Use

- Any task requiring programmatic generation of production moodboards (PNG format)
- When you need to create visual collages with reference images programmatically
- When standard moodboard software is unavailable or batch generation is needed
- Any deliverable requiring consistent, reproducible moodboard layouts

## One-Line Summary

Generate professional-grade moodboards programmatically using PIL/Pillow by creating a structured canvas, placing reference images in a grid layout, and adding color swatches with labels.

---

## Main Body

### Step 1: Define Canvas Structure

```python
from PIL import Image, ImageDraw, ImageFont

# Standard moodboard dimensions
MOODBOARD_WIDTH = 1920
MOODBOARD_HEIGHT = 1080  # or 2400 for vertical scroll format

# Create base canvas
canvas = Image.new('RGB', (MOODBOARD_WIDTH, MOODBOARD_HEIGHT), '#1a1a1a')
draw = ImageDraw.Draw(canvas)
```

### Step 2: Layout Zones

Divide the canvas into logical zones:

| Zone | Purpose | Typical Size/Position |
|------|---------|----------------------|
| Title Area | Project name, description | Top 80px |
| Color Palette Section | Swatches with hex codes | 100px height |
| Reference Grid | Photographic images | Main body |
| Notes Section | Text descriptions | Bottom 100px |

### Step 3: Load and Place Reference Images

**CRITICAL**: Reference images must be actual photographs, not abstract shapes.

```python
def load_reference_image(path, target_size):
    """Load and resize reference image maintaining aspect ratio."""
    img = Image.open(path)
    img.thumbnail(target_size, Image.Resampling.LANCZOS)
    return img

# Calculate grid positions
GRID_COLS = 4
GRID_ROWS = 3
CELL_WIDTH = (CANVAS_WIDTH - MARGIN * (GRID_COLS + 1)) // GRID_COLS
CELL_HEIGHT = (CANVAS_HEIGHT - TOP_SECTION - BOTTOM_SECTION - 
               MARGIN * (GRID_ROWS + 1)) // GRID_ROWS
```

### Step 4: Add Color Swatches

```python
def add_color_swatches(draw, colors, start_y, swatch_size=80):
    """
    colors: List of tuples (color_name, hex_code)
    Example: [("Primary Red", "#8B0000"), ...]
    """
    x = LEFT_MARGIN
    for color_name, hex_code in colors:
        # Draw swatch rectangle
        draw.rectangle(
            [(x, start_y), (x + swatch_size, start_y + swatch_size)],
            fill=hex_code,
            outline='#ffffff',
            width=2
        )
        # Add label
        draw.text(
            (x, start_y + swatch_size + 10),
            f"{color_name}\n{hex_code}",
            fill='#ffffff'
        )
        x += swatch_size + SPACING
```

### Step 5: Render and Export

```python
# Save as PNG for production use
canvas.save('moodboard.png', 'PNG', quality=95)

# Optional: Save as JPEG with high quality
canvas.save('moodboard.jpg', 'JPEG', quality=95, optimize=True)
```

---

## Examples

### Example: Basic Music Video Moodboard

**Scenario**: Creating a moodboard for a cinematic ballad with dark, moody aesthetic.

```python
from PIL import Image, ImageDraw, ImageFont

def create_moodboard(title, description, color_palette, image_paths):
    # Canvas setup
    canvas = Image.new('RGB', (1920, 1200), '#0a0a0a')
    draw = ImageDraw.Draw(canvas)
    
    # Title section
    draw.text((50, 30), title, fill='#ffffff', font=title_font)
    draw.text((50, 70), description, fill='#cccccc', font=body_font)
    
    # Color palette section (at y=120)
    y_palette = 120
    x_pos = 50
    for color_name, hex_code in color_palette:
        draw.rectangle([(x_pos, y_palette), (x_pos+100, y_palette+60)], 
                      fill=hex_code, outline='#ffffff')
        draw.text((x_pos, y_palette+70), color_name, fill='#ffffff')
        x_pos += 130
    
    # Reference image grid (starting at y=250)
    grid_start_y = 250
    cols, rows = 3, 2
    img_width = (1920 - 100 - (cols-1)*20) // cols
    img_height = 350
    
    for i, img_path in enumerate(image_paths[:6]):
        row, col = i // cols, i % cols
        x = 50 + col * (img_width + 20)
        y = grid_start_y + row * (img_height + 20)
        
        img = Image.open(img_path)
        img.thumbnail((img_width, img_height), Image.Resampling.LANCZOS)
        canvas.paste(img, (x, y))
        
        # Add thin border
        draw.rectangle([(x, y), (x+img.width, y+img.height)], 
                      outline='#444444', width=1)
    
    return canvas

# Usage
color_palette = [
    ("Deep Crimson", "#8B0000"),
    ("Midnight Blue", "#191970"),
    ("Antique Gold", "#D4AF37")
]

moodboard = create_moodboard(
    title="Cinematic Ballad - Visual Direction",
    description="Dark, emotional aesthetic with rich contrasts",
    color_palette=color_palette,
    image_paths=["ref1.jpg", "ref2.jpg", "ref3.jpg", ...]
)
moodboard.save('output_moodboard.png')
```

---

## Code Demo

### Complete Production-Ready Template

```python
"""
Moodboard Generator for Production Use
Supports: PNG output, configurable layouts, color swatches, image grids
"""

from PIL import Image, ImageDraw, ImageFont
import os

class MoodboardGenerator:
    def __init__(self, width=1920, height=1200, bg_color='#1a1a1a'):
        self.width = width
        self.height = height
        self.canvas = Image.new('RGB', (width, height), bg_color)
        self.draw = ImageDraw.Draw(self.canvas)
        
        # Try to load fonts, fallback to default
        try:
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            self.body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            self.title_font = ImageFont.load_default()
            self.body_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
    
    def add_title(self, title, subtitle=None, y_pos=30):
        """Add title and optional subtitle at specified y position."""
        self.draw.text((50, y_pos), title, fill='#ffffff', font=self.title_font)
        if subtitle:
            self.draw.text((50, y_pos + 50), subtitle, fill='#aaaaaa', font=self.body_font)
    
    def add_color_palette(self, colors, y_pos=120, swatch_size=60):
        """
        Add color swatches with labels.
        colors: List of (name, hex_code) tuples
        """
        x = 50
        for name, hex_code in colors:
            # Swatch
            self.draw.rectangle(
                [(x, y_pos), (x + swatch_size, y_pos + swatch_size)],
                fill=hex_code,
                outline='#ffffff',
                width=2
            )
            # Name label
            self.draw.text((x, y_pos + swatch_size + 8), name, 
                          fill='#ffffff', font=self.small_font)
            # Hex code label
            self.draw.text((x, y_pos + swatch_size + 25), hex_code, 
                          fill='#aaaaaa', font=self.small_font)
            x += swatch_size + 30
    
    def add_image_grid(self, image_paths, y_pos=250, 
                       cols=3, max_rows=2, padding=20):
        """
        Add grid of reference images.
        Returns list of successfully loaded images.
        """
        available_width = self.width - 100 - (cols - 1) * padding
        cell_width = available_width // cols
        cell_height = (self.height - y_pos - 150 - (max_rows - 1) * padding) // max_rows
        
        loaded = []
        for i, path in enumerate(image_paths[:cols * max_rows]):
            if not os.path.exists(path):
                print(f"Warning: Image not found: {path}")
                continue
                
            row, col = i // cols, i % cols
            x = 50 + col * (cell_width + padding)
            y = y_pos + row * (cell_height + padding)
            
            try:
                img = Image.open(path)
                # Resize to fit cell while maintaining aspect ratio
                img.thumbnail((cell_width, cell_height), Image.Resampling.LANCZOS)
                self.canvas.paste(img, (x, y))
                
                # Add subtle border
                self.draw.rectangle(
                    [(x, y), (x + img.width, y + img.height)],
                    outline='#444444',
                    width=1
                )
                loaded.append(path)
            except Exception as e:
                print(f"Error loading {path}: {e}")
        
        return loaded
    
    def save(self, filepath, format='PNG'):
        """Save moodboard to file."""
        self.canvas.save(filepath, format)
        print(f"Moodboard saved to: {filepath}")
        return filepath


# USAGE EXAMPLE
if __name__ == "__main__":
    gen = MoodboardGenerator(width=1920, height=1200)
    
    gen.add_title(
        "PROJECT: The Artist - Music Video",
        subtitle="Visual Direction: Baroque Masquerade meets Surreal Gothic"
    )
    
    gen.add_color_palette([
        ("Deep Crimson", "#8B0000"),
        ("Antique Gold", "#D4AF37"),
        ("Midnight Blue", "#191970"),
        ("Victorian Brown", "#5C4033"),
        ("Sage Green", "#9DC183")
    ])
    
    # Load actual photographic references
    reference_images = [
        "references/costume_ref1.jpg",
        "references/lighting_ref1.jpg", 
        "references/set_ref1.jpg",
        "references/cinematography_ref1.jpg",
        "references/makeup_ref1.jpg",
        "references/props_ref1.jpg"
    ]
    
    gen.add_image_grid(reference_images, cols=3, max_rows=2)
    gen.save('production_moodboard.png')
```

---

## Key Takeaways

1. **Always use actual images**: Never substitute with geometric shapes or color blocks
2. **Maintain aspect ratios**: Use `thumbnail()` not `resize()` to avoid distortion
3. **Consistent spacing**: Use variables for margins and padding
4. **Error handling**: Gracefully handle missing or corrupt image files
5. **Export quality**: Use PNG for lossless quality, JPEG at 95%+ for smaller files

## References

- PIL/Pillow Documentation: https://pillow.readthedocs.io/
- Milanote Film Moodboard Guide: https://milanote.com/guide/film-moodboard
- StudioBinder Mood Board Tutorial: https://www.studiobinder.com/blog/how-to-make-a-film-mood-board/
