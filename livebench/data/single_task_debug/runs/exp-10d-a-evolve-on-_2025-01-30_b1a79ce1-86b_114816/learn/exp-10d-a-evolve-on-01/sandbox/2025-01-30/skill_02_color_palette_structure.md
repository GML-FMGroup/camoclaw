---
type: technical
skill_name: Production Color Palette Structure for Film/Video Moodboards
---

## When to Use
- Any video production moodboard requiring a defined color palette section
- Music videos, commercials, or film projects with specific visual themes
- Projects where color grading, costume, or production design must align with creative direction
- Moodboards that need to communicate emotional tone through color

## One-Line Summary
Structure the color palette with named swatches, hex/RGB values, and descriptive labels that connect colors to mood, character, or scene purpose.

## Main Body

### Required Color Palette Elements

1. **Named Swatches**: Each color must have a descriptive name (e.g., "Deep Crimson", "Antique Gold", not just "Red" or "Yellow")
2. **Hex/RGB Values**: Include technical color codes for production use (#HEX or RGB format)
3. **Usage Context**: Label what each color represents (primary, accent, shadow, highlight, character costume, background, etc.)
4. **Visual Placement**: Display swatches as actual colored rectangles/blocks, not text-only descriptions

### Color Categories to Include

For a comprehensive production palette, organize by:

- **Primary Palette**: 3-5 dominant colors that define the overall look
- **Secondary/Accent Colors**: Supporting colors for contrast and visual interest
- **Neutral/Foundation**: Base colors (whites, grays, blacks) for balance
- **Emotional Associations**: Brief note on what emotion or meaning each color conveys

### Layout Guidelines

```
┌─────────────────────────────────────────────────────────────┐
│  COLOR PALETTE - [Project Name]                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PRIMARY                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │████ Deep  │ │████ Gold │ │████ Vint │                     │
│  │████Crimson│ │████Accent│ │████Brown │                     │
│  │ #8B0000  │ │ #D4AF37  │ │ #5C4033  │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
│                                                             │
│  SECONDARY                                                  │
│  ┌──────────┐ ┌──────────┐                                  │
│  │████ Satin│ │████Shadow │                                  │
│  │████Black │ │████Teal  │                                  │
│  │ #0C0C0C  │ │ #008080  │                                  │
│  └──────────┘ └──────────┘                                  │
└─────────────────────────────────────────────────────────────┘
```

## Examples

### Example 1: Baroque Masquerade Palette
```
Deep Crimson (#8B0000) - Primary, for velvet costumes and dramatic lighting
Antique Gold (#D4AF37) - Accent, for masks and ornamental details  
Victorian Brown (#5C4033) - Secondary, for set backgrounds and wood tones
Midnight Teal (#008080) - Shadow color, for depth and mystery
Satin Black (#0C0C0C) - Foundation, for contrast and silhouettes
```

### Example 2: Minimalist Drama Palette
```
Warm Ivory (#FFFFF0) - Primary background, for clean, open spaces
Charcoal (#36454F) - Primary contrast, for costumes and props
Muted Rose (#D4A5A5) - Accent, for subtle emotional warmth
Deep Navy (#000080) - Shadow/depth color
```

## Code Demo (Python/PIL)

```python
from PIL import Image, ImageDraw, ImageFont

def create_color_palette_swatches(colors, output_path):
    """
    Create visual color palette swatches.
    
    Args:
        colors: List of dicts with 'name', 'hex', and 'usage' keys
        output_path: Where to save the palette image
    """
    swatch_width = 200
    swatch_height = 150
    cols = 3
    rows = (len(colors) + cols - 1) // cols
    
    img_width = swatch_width * cols + 40
    img_height = swatch_height * rows + 60
    
    img = Image.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Title
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    draw.text((20, 10), "COLOR PALETTE", fill='black', font=font_title)
    
    # Draw swatches
    for i, color in enumerate(colors):
        col = i % cols
        row = i // cols
        x = 20 + col * (swatch_width + 10)
        y = 50 + row * (swatch_height + 10)
        
        # Draw color block
        hex_color = color['hex'].lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        draw.rectangle([x, y, x + swatch_width, y + 80], fill=rgb)
        
        # Draw labels
        draw.text((x, y + 85), color['name'], fill='black', font=font_text)
        draw.text((x, y + 105), color['hex'], fill='gray', font=font_text)
        draw.text((x, y + 125), color['usage'], fill='gray', font=font_text)
    
    img.save(output_path)
    return output_path

# Example usage
colors = [
    {'name': 'Deep Crimson', 'hex': '#8B0000', 'usage': 'Primary - Costumes'},
    {'name': 'Antique Gold', 'hex': '#D4AF37', 'usage': 'Accent - Details'},
    {'name': 'Victorian Brown', 'hex': '#5C4033', 'usage': 'Secondary - Sets'},
]
create_color_palette_swatches(colors, '/tmp/palette.png')
```

## Key Takeaway
A production-ready color palette must be both visually displayed (as actual color blocks) and technically documented (with hex/RGB values and usage context). Text descriptions alone are insufficient for professional production use.
