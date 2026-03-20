# Skill: Creating Professional Stage Plot Graphics with Python

type: technical

## When to Use

- Any stage plot task requiring visual diagrams exported as PDF
- Creating icons for microphones, DI boxes, amps, monitors, instruments
- Drawing scaled stage diagrams with proper placement
- Generating touring advance documents with embedded graphics
- Any Python-based diagram generation for live sound documentation

## One-Line Summary

Use matplotlib with reportlab to create scalable stage plot graphics with standardized icons, proper scaling, and PDF export.

## Main Body

### Core Principles

1. **Use matplotlib for the visual diagram** - Matplotlib provides precise control over shapes, positions, and scaling needed for technical diagrams
2. **Export to PDF via reportlab** - ReportLab integrates matplotlib figures into professional PDF documents
3. **Maintain aspect ratio** - Stage plots should typically use landscape orientation (width > height)
4. **Standard icon sizes** - Use consistent sizes: mics/DIs (small circles ~0.3 units), amps (rectangles ~1.0 x 0.6 units), wedges (triangles ~0.5 units)

### Required Libraries

```python
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Circle, Rectangle, Polygon, FancyBboxPatch
import io
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Image, Spacer, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
```

### Icon Drawing Standards

| Item | Shape | Color | Size Reference |
|------|-------|-------|----------------|
| Vocal Microphone | Circle with X | Black fill | radius=0.15 |
| DI Box | Small rectangle | Gray fill | 0.2 x 0.15 |
| Guitar/Bass Amp | Larger rectangle | Black outline | 0.6 x 0.4 |
| Monitor Wedge | Triangle (pointing up) | Blue fill | base=0.4, height=0.3 |
| Drum Kit | Circle cluster | Various | Kit diagram |
| IEM Transmitter | Small square | Green fill | 0.15 x 0.15 |

### Layout Guidelines

1. **Stage orientation**: Always label Stage Right (audience's right, performer's left) and Stage Left
2. **Front-of-stage indicator**: Place at bottom of diagram
3. **Scale**: 1 unit ≈ 2-3 feet for typical club stages
4. **Member spacing**: Leave at least 1.5 units between band members
5. **Monitor placement**: Wedges should face the performer at ~45° angle

### Rendering Pipeline

```
1. Create matplotlib figure with figsize=(11, 8.5) for landscape
2. Set axis limits to define stage boundaries (e.g., x: 0-10, y: 0-8)
3. Draw stage boundary/outline
4. Draw each band member position with label
5. Draw all equipment icons at correct (x, y) coordinates
6. Add legend/key for symbols
7. Save to BytesIO buffer as PNG
8. Embed in ReportLab PDF with input/output lists
```

## Examples

### Example 1: Drawing a Monitor Wedge

Scenario: A vocalist needs a wedge placed at their 10 o'clock position (front-left).

```
Position: (x_performer - 0.8, y_performer + 0.5)
Angle: 45° pointing toward performer
Symbol: Triangle with apex pointing toward performer
Label: "Wedge N" near the icon
```

### Example 2: Drawing an XLR Split Configuration

Scenario: A vocalist uses IEM with XLR split - one to FOH, one to IEM pack.

```
On stage plot:
- Draw vocal mic at performer's position
- Draw small "split" indicator (Y-shape) next to mic
- Label: "Vox N (split)" or use line annotation

On input list:
- Channel N: "Vox N - FOH"
- Channel N+1: "Vox N - IEM" (if separate channel)

On output list:
- Output N: "Vox N IEM Transmit"
```

### Example 3: Complete Stage Dimensions

Scenario: 5-piece band on standard club stage (~24ft wide x 16ft deep).

```
Stage coordinates (matplotlib units):
- Stage width: 0 to 10
- Stage depth: 0 to 7 (0 = upstage/back, 7 = downstage/front)
- Drummer at y=1.5 (upstage)
- Vocalists at y=5 (downstage)
- Front-of-stage at y=7
```

## Code Demo

```python
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Circle, Rectangle, Polygon, FancyBboxPatch
import io
import numpy as np

def create_stage_plot():
    """
    Creates a professional stage plot diagram.
    Returns: BytesIO buffer containing PNG image
    """
    # Create figure - landscape orientation
    fig, ax = plt.subplots(figsize=(11, 8.5))
    
    # Set stage boundaries
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Draw stage outline
    stage = Rectangle((0.5, 0.5), 9, 7, linewidth=2, 
                      edgecolor='black', facecolor='lightgray', alpha=0.3)
    ax.add_patch(stage)
    
    # Add "FRONT OF STAGE" indicator at bottom
    ax.annotate('FRONT OF STAGE', xy=(5, 0.2), fontsize=14, 
                ha='center', fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
    
    # Stage Right / Stage Left labels
    ax.text(0.2, 4, 'STAGE RIGHT', rotation=90, fontsize=10, 
            va='center', ha='center')
    ax.text(9.8, 4, 'STAGE LEFT', rotation=270, fontsize=10, 
            va='center', ha='center')
    
    return fig, ax

def draw_microphone(ax, x, y, label=None, color='black'):
    """Draw a vocal microphone icon (circle with X)"""
    # Outer circle
    mic = Circle((x, y), 0.15, facecolor=color, edgecolor='black', linewidth=1)
    ax.add_patch(mic)
    # X inside
    ax.plot([x-0.08, x+0.08], [y-0.08, y+0.08], 'w-', linewidth=1.5)
    ax.plot([x-0.08, x+0.08], [y+0.08, y-0.08], 'w-', linewidth=1.5)
    if label:
        ax.text(x, y-0.35, label, ha='center', va='top', fontsize=8)

def draw_di_box(ax, x, y, label=None):
    """Draw a DI box icon (small rectangle)"""
    di = Rectangle((x-0.1, y-0.075), 0.2, 0.15, 
                   facecolor='gray', edgecolor='black', linewidth=1)
    ax.add_patch(di)
    if label:
        ax.text(x, y-0.25, label, ha='center', va='top', fontsize=7)

def draw_amp(ax, x, y, label=None, width=0.6, height=0.4):
    """Draw an amplifier icon (rectangle)"""
    amp = Rectangle((x-width/2, y-height/2), width, height,
                    facecolor='lightgray', edgecolor='black', linewidth=2)
    ax.add_patch(amp)
    # Grill lines
    for i in range(3):
        y_line = y - height/2 + (height/4) * (i + 0.5)
        ax.plot([x-width/2+0.05, x+width/2-0.05], [y_line, y_line], 'k-', linewidth=0.5)
    if label:
        ax.text(x, y-height/2-0.15, label, ha='center', va='top', fontsize=8)

def draw_wedge(ax, x, y, angle=0, label=None, color='#4169E1'):
    """
    Draw a monitor wedge icon (triangle)
    angle: rotation in degrees (0 = pointing up/north)
    """
    # Create triangle pointing up by default
    triangle = np.array([[0, 0.3], [-0.25, -0.2], [0.25, -0.2]])
    
    # Rotate
    theta = np.radians(angle)
    rotation = np.array([[np.cos(theta), -np.sin(theta)],
                         [np.sin(theta), np.cos(theta)]])
    rotated = np.dot(triangle, rotation.T)
    
    # Translate to position
    wedge_points = rotated + np.array([x, y])
    
    wedge = Polygon(wedge_points, facecolor=color, edgecolor='black', linewidth=1)
    ax.add_patch(wedge)
    
    if label:
        ax.text(x, y-0.35, label, ha='center', va='top', fontsize=7)

def draw_drum_kit(ax, x, y, label="Drums"):
    """Draw a simplified drum kit icon"""
    # Bass drum
    bass = Circle((x, y), 0.4, facecolor='white', edgecolor='black', linewidth=2)
    ax.add_patch(bass)
    # Snare
    snare = Circle((x+0.5, y+0.3), 0.2, facecolor='white', edgecolor='black', linewidth=1)
    ax.add_patch(snare)
    # Floor tom
    floor = Circle((x-0.4, y+0.2), 0.25, facecolor='white', edgecolor='black', linewidth=1)
    ax.add_patch(floor)
    # Cymbal stands (simplified as lines)
    ax.plot([x+0.3, x+0.3], [y+0.4, y+0.8], 'k-', linewidth=2)
    ax.plot([x-0.2, x-0.2], [y+0.5, y+0.9], 'k-', linewidth=2)
    
    ax.text(x, y-0.6, label, ha='center', va='top', fontsize=9, fontweight='bold')

def save_to_buffer(fig):
    """Save matplotlib figure to BytesIO buffer for ReportLab"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

def create_stage_plot_pdf(band_name, stage_plot_buffer, input_list_data, output_list_data):
    """
    Create complete PDF with stage plot and lists
    
    stage_plot_buffer: BytesIO from save_to_buffer()
    input_list_data: list of dicts with channel, input_name, mic_type, location
    output_list_data: list of dicts with output, destination, source
    """
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Image, Spacer, Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    
    # Create PDF
    pdf_path = "/tmp/stage_plot.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=landscape(letter),
                           rightMargin=36, leftMargin=36,
                           topMargin=36, bottomMargin=36)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(f"<b>STAGE PLOT - {band_name}</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Stage plot image
    stage_img = Image(stage_plot_buffer, width=500, height=380)
    elements.append(stage_img)
    elements.append(Spacer(1, 12))
    
    # Input List Table
    input_data = [['Channel', 'Input', 'Mic/DI Type', 'Location']]
    for row in input_list_data:
        input_data.append([row['channel'], row['input_name'], 
                          row['mic_type'], row['location']])
    
    input_table = Table(input_data)
    input_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(Paragraph("<b>INPUT LIST</b>", styles['Heading2']))
    elements.append(input_table)
    elements.append(Spacer(1, 12))
    
    # Output List Table
    output_data = [['Output', 'Destination', 'Source/Mix']]
    for row in output_list_data:
        output_data.append([row['output'], row['destination'], row['source']])
    
    output_table = Table(output_data)
    output_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(Paragraph("<b>OUTPUT LIST</b>", styles['Heading2']))
    elements.append(output_table)
    
    doc.build(elements)
    return pdf_path

# Example usage:
if __name__ == "__main__":
    fig, ax = create_stage_plot()
    
    # Draw example band setup
    draw_drum_kit(ax, 5, 2, "Drums")
    draw_microphone(ax, 5, 2.8, "Drum Vox")
    draw_wedge(ax, 4.2, 2.5, angle=45, label="Wedge 5")
    
    draw_microphone(ax, 3, 5, "Vox 1")
    draw_wedge(ax, 2.5, 4.5, angle=30, label="Wedge 1")
    
    draw_microphone(ax, 7, 5, "Vox 2")
    draw_wedge(ax, 7.5, 4.5, angle=-30, label="Wedge 2")
    
    draw_amp(ax, 1.5, 5, "Guitar Amp")
    draw_wedge(ax, 2, 4.5, angle=30, label="Wedge 3")
    
    draw_amp(ax, 8.5, 5, "Bass Amp")
    draw_microphone(ax, 8.5, 5.6, "Bass Vox")
    draw_wedge(ax, 8, 4.5, angle=-30, label="Wedge 4")
    draw_di_box(ax, 8.2, 4.2, "DI 1")
    draw_di_box(ax, 8.8, 4.2, "DI 2")
    
    buf = save_to_buffer(fig)
    
    # Example input list
    input_list = [
        {'channel': '1', 'input_name': 'Kick', 'mic_type': 'Beta 52', 'location': 'Drums'},
        {'channel': '2', 'input_name': 'Snare', 'mic_type': 'SM57', 'location': 'Drums'},
        {'channel': '3', 'input_name': 'Vox 1', 'mic_type': 'SM58', 'location': 'Stage Right'},
        {'channel': '4', 'input_name': 'Vox 2', 'mic_type': 'SM58', 'location': 'Stage Left'},
    ]
    
    # Example output list
    output_list = [
        {'output': '1', 'destination': 'Wedge 1', 'source': 'Vox 1 Mix'},
        {'output': '2', 'destination': 'Wedge 2', 'source': 'Vox 2 Mix'},
        {'output': '5', 'destination': 'Wedge 5', 'source': 'Drum Mix'},
    ]
    
    pdf_path = create_stage_plot_pdf("Example Band", buf, input_list, output_list)
    print(f"PDF saved to: {pdf_path}")
```

## Critical Reminders

1. **ALWAYS verify that every item in Input List has an icon on the plot**
2. **ALWAYS verify that every item in Output List has an icon on the plot**
3. **Use the checklist in Skill 01 before finalizing**
4. **Save matplotlib figure before closing (plt.close()) to avoid empty images**
5. **Seek buffer to position 0 (buf.seek(0)) before passing to ReportLab**
