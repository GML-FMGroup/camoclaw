# Stage Layout Conventions and PDF Formatting Standards

type: strategy

## When to Use

- Creating one-page stage plot PDFs for venue advance packages
- Determining orientation and positioning for touring documentation
- Establishing industry-standard stage layout conventions (Stage Left/Right, front-of-house positioning)
- Ensuring professional visual standards in deliverables

## One-Line Summary

Apply industry-standard stage orientation conventions (performer's perspective), landscape layout with front-of-house at the bottom, and one-page PDF format for venue advance documentation.

## Main Body

### Stage Orientation Standards

**Stage Left vs. Stage Right:**
- **ALWAYS use PERFORMER'S perspective** when labeling stage positions
- Stage Left (SL): Performer's left when facing the audience (audience's right)
- Stage Right (SR): Performer's right when facing the audience (audience's left)
- **Critical:** Do NOT use audience perspective - this is a common error that confuses venue staff

**Positioning Conventions:**
- Drummer typically placed center-upstage or upstage-left
- Main performers downstage (closer to audience)
- Amps and backline positioned upstage of performers
- Monitor wedges placed downstage of each performer's position

### PDF Layout Requirements

**Page Format:**
- **Orientation:** Landscape (horizontal) - provides maximum width for stage representation
- **Size:** Standard Letter (11" x 8.5") or A4 (297mm x 210mm)
- **One-page constraint:** All essential information must fit on a single page

**Diagram Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  [Band Name]                    [Legend]    [Input List]   │
│                                                             │
│     ○                    ○                    ○            │
│    Vox1                 Vox2                Drummer        │
│                                                             │
│  ════════   Stage Edge/Front-of-Stage  ════════            │
│                    (Audience Side)                          │
└─────────────────────────────────────────────────────────────┘
```

**Critical Layout Rule:**
- Front-of-Stage (audience side) MUST be at the **BOTTOM** of the diagram
- Back-of-Stage (drummer/amps) at the **TOP**
- This matches the performer's view when facing the audience

### Legend Requirements

Include a visual legend explaining all symbols used:

| Symbol | Meaning |
|--------|---------|
| Ⓧ (circle with X) | Microphone |
| ▭ (rectangle) | Amplifier |
| △ (triangle) | Monitor wedge |
| ◻ (small square) | DI box |
| ⧖ (hourglass/I) | IEM transmitter |
| ⌀ (concentric circles) | Drum kit |

### Visual Consistency Checklist

- [ ] **Stage orientation correct:** Performer's perspective used throughout
- [ ] **Front-of-stage at bottom:** Audience side shown at bottom of diagram
- [ ] **Landscape format:** Page oriented horizontally
- [ ] **One-page limit:** All content fits without scaling
- [ ] **Legend included:** All symbols explained with clear visual reference
- [ ] **Consistent icon sizing:** All icons proportionally sized and aligned
- [ ] **Label legibility:** All text readable at print size (minimum 8pt font)
- [ ] **Professional appearance:** Clean lines, proper spacing, no clutter

### Python PDF Layout Code Demo

```python
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch

def create_stage_plot_pdf(output_path):
    """
    Create a professional one-page landscape stage plot PDF.
    """
    # Set up landscape letter size
    width, height = landscape(letter)
    
    c = canvas.Canvas(output_path, pagesize=landscape(letter))
    
    # Margins
    margin = 0.5 * inch
    
    # Header area at top
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, height - margin - 20, "[Band Name] - Stage Plot")
    
    # Main stage area - front-of-stage at BOTTOM (y = margin + stage_height)
    stage_top = height - margin - 60
    stage_bottom = margin + 100  # Leave room for front-of-stage label
    stage_left = margin + 80     # Leave room for Stage Left label
    stage_right = width - margin - 80  # Leave room for Stage Right label
    
    # Draw stage boundary
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(2)
    c.rect(stage_left, stage_bottom, 
           stage_right - stage_left, 
           stage_top - stage_bottom, 
           stroke=1, fill=0)
    
    # Front-of-stage label at BOTTOM (audience side)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(
        (stage_left + stage_right) / 2,
        stage_bottom - 30,
        "FRONT OF STAGE (Audience)"
    )
    
    # Stage Left/Right labels (performer perspective)
    c.saveState()
    c.translate(margin + 20, (stage_top + stage_bottom) / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, "STAGE LEFT")
    c.restoreState()
    
    c.saveState()
    c.translate(width - margin - 20, (stage_top + stage_bottom) / 2)
    c.rotate(-90)
    c.drawCentredString(0, 0, "STAGE RIGHT")
    c.restoreState()
    
    # Legend box
    legend_x = stage_right + 20
    legend_y = stage_top - 150
    c.setFont("Helvetica-Bold", 10)
    c.drawString(legend_x, legend_y, "LEGEND:")
    
    legend_items = [
        ("Ⓧ  = Microphone", legend_y - 20),
        ("▭  = Amplifier", legend_y - 35),
        ("△  = Wedge Monitor", legend_y - 50),
        ("◻  = DI Box", legend_y - 65),
    ]
    
    c.setFont("Helvetica", 9)
    for text, y_pos in legend_items:
        c.drawString(legend_x, y_pos, text)
    
    c.save()
    return output_path

# Usage
# create_stage_plot_pdf("/tmp/stage_plot.pdf")
```

## Examples

### Example 1: Standard 5-Piece Band Layout
```
Performer Setup:
- Vox1 at Stage Right downstage position
- Vox2 at Stage Left downstage position  
- Drummer center-upstage
- Guitarist stage left (audience's right)
- Bassist stage right (audience's left)

Stage Layout:
Back of Stage (Top)
    [Drummer + Kit]     [Guitar Amp]
         ○
        Vox2            [Bass Amp]
   [Wedge2]  [Wedge1]
═══════════════════════════
      FRONT OF STAGE (Bottom)
```

### Example 2: IEM and Wedge Combination Layout
```
Monitor Configuration:
- Vox1: IEM pack + Wedge1 for vocal fill
- Vox2: IEM pack + Wedge2 for vocal fill  
- Drummer: Wedge3 at 10 o'clock position
- Guitarist: Wedge4 with guitar feed
- Bassist: Wedge5 with bass fill

Output List Mapping:
- Out 1-2: IEM L/R (Vox1)
- Out 3-4: IEM L/R (Vox2)
- Out 5: Wedge1 (Vox1 vocal fill)
- Out 6: Wedge2 (Vox2 vocal fill)
- Out 7: Wedge3 (Drummer - Vox1+Vox2 mix)
- Out 8: Wedge4 (Guitarist)
- Out 9: Wedge5 (Bassist)
```

## Key Takeaways

1. **Performer Perspective:** Always use Stage Left/Right from the performer's view facing the audience
2. **Bottom-Front Rule:** Audience side must be at the bottom of the diagram
3. **Landscape Format:** One-page landscape is the touring industry standard
4. **Visual Hierarchy:** Stage plot diagram should be the largest element; input/output lists secondary
5. **Professional Standards:** Clean, legible, properly scaled graphics that print clearly

## Common Layout Mistakes to Avoid

| Mistake | Correction |
|---------|------------|
| Audience perspective for stage labels | Use performer perspective |
| Front-of-stage at top of diagram | Move to bottom |
| Portrait orientation | Use landscape |
| Missing legend | Always include symbol key |
| Overcrowded single page | Prioritize essential elements |
| Inconsistent icon sizing | Use standardized symbol dimensions |
