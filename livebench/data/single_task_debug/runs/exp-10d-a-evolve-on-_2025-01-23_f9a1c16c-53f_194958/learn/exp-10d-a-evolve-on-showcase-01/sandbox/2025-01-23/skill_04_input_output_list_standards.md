# Skill: Input List and Output List Standards for Touring Advance Documentation

type: technical

---

## When to Use

- Creating technical riders for touring bands or live productions
- Advancing shows with venue production staff
- Documenting signal flow for monitor engineers and FOH engineers
- Any stage plot that requires accompanying channel lists or signal routing documentation
- Preparing advance packages for load-in and setup coordination

---

## One-Line Summary

Every item listed in input/output lists must have a corresponding visual representation on the stage plot, and channel assignments must follow logical grouping with clear signal flow notation.

---

## Main Body

### 1. Input List Structure

The input list documents every audio source entering the console. Standard fields include:

| Field | Purpose | Example |
|-------|---------|---------|
| Channel | Console channel number | 1, 2, 3... |
| Input | Source name | Kick Drum, Vox 1, Bass DI |
| Mic/DI | Recommended microphone or DI type | Beta 52, SM58, Radial J48 |
| Stand | Stand type needed | Short boom, Straight, Low profile |
| Position | Physical location on stage | DS Center, SR, 10 o'clock Drums |
| Notes | Special routing or processing | Split to IEM, 48V required |

**Ordering Convention:**
- Drums first (Kick, Snare, Hats, Toms, Overheads)
- Bass
- Guitars
- Keyboards/Other instruments
- Vocals last (Lead Vox, BV1, BV2, Drum Vox, etc.)

### 2. Output List Structure

The output list documents monitor mixes, IEM feeds, and auxiliary sends. Standard fields include:

| Field | Purpose | Example |
|-------|---------|---------|
| Output | Aux/Monitor output number | Aux 1, Aux 2... |
| Destination | What receives the mix | Wedge 1 (Vox1), IEM L (Drummer) |
| Contents | What's in the mix | Vox1, Vox2, Click |
| Location | Physical placement on stage | SR, 10 o'clock Drums, SL |
| Notes | Special requirements | Stereo feed, Needs vocal priority |

### 3. The Completeness Rule (Critical)

**EVERY item in your Input List and Output List MUST have a corresponding visual icon on the stage plot.**

This is the #1 failure mode in touring advance documentation. Common omissions:

- ✅ IEM belt packs shown but not the corresponding antennas/transmitters
- ✅ Wedges listed in Output List but not drawn on stage
- ✅ Microphones in Input List but not placed near performers
- ✅ DIs mentioned but not positioned at instruments

**Verification Checklist:**
- [ ] Count inputs in Input List → Count input icons on plot (must match)
- [ ] Count outputs in Output List → Count output icons on plot (must match)
- [ ] Each wedge has a triangle icon on stage
- [ ] Each IEM has a pack icon on the performer
- [ ] Each amp has a rectangle icon
- [ ] Each DI has a box icon near the instrument

### 4. Signal Flow Notation

For IEM splits and complex routing, use standard notation:

| Notation | Meaning |
|----------|---------|
| Mic → Split | XLR split between FOH and IEM |
| DI → FOH | Direct box feeds FOH only |
| Aux N → Wedge N | Auxiliary send feeds floor wedge |
| IEM L/R | Stereo in-ear monitor feed |

---

## Examples

### Example 1: Basic Input List

```
INPUT LIST - Band Name
Ch | Input       | Mic/DI    | Position        | Notes
---+-------------+-----------+-----------------+------------------
1  | Kick        | Beta 52   | DS Center Drums | 
2  | Snare       | SM57      | Center Drums    |
3  | Hat         | SM81      | Drummer left    |
4  | OH L        | KSM32     | DL Drums        |
5  | OH R        | KSM32     | DR Drums        |
6  | Bass        | DI        | SR - Bass rig   | Amp has DI out
7  | Guitar      | DI        | SL - Guitar rig | Amp has DI out
8  | Acoustic    | DI        | SR              | Accordion DI
9  | Vox 1       | SM58      | SR              | Split to IEM
10 | Vox 2       | SM58      | SL              | Split to IEM
11 | Vox Drums   | SM58      | Drums           | Short boom
12 | Vox Bass    | SM58      | SR              | Short boom
```

### Example 2: Output List with IEM and Wedges

```
OUTPUT LIST - Band Name
Output | Destination | Location          | Contents              | Notes
-------+-------------+-------------------+-----------------------+------------------
Aux 1  | IEM L       | Drummer           | Mix L                 | Stereo pair
Aux 2  | IEM R       | Drummer           | Mix R                 | Stereo pair
Aux 3  | Wedge 1     | SR (Vox1)         | Vox1, Vox2            | Vox priority
Aux 4  | Wedge 2     | SL (Vox2)         | Vox2, Vox1            | Vox priority
Aux 5  | Wedge 3     | 10 o'clock Drums  | Vox1, Vox2, Drums     | Drummer's wedge
Aux 6  | Wedge 4     | SL (Guitar)       | Guitar                | Guitar fill
Aux 7  | Wedge 5     | SR (Bass)         | Bass                  | Bass fill
```

**Critical Check:** The stage plot must show:
- 2 IEM belt packs (one on drummer, one on vocalist if applicable)
- 5 wedge triangles at the specified locations
- All 12 input sources positioned correctly

### Example 3: Split Configuration for IEMs

```
Vocal Mic Signal Flow:

Mic ──→ Splitter Box ──→ Split A ──→ FOH Console Ch N
              │
              └──→ Split B ──→ IEM Transmitter ──→ IEM Pack

Stage Plot Icon: Show both the mic AND the IEM belt pack on the performer
Input List: Note "Split to IEM" in Notes column
Output List: Include IEM feed in outputs
```

---

## Code Demo

### Generating Input/Output Lists as Tables in PDF

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def create_input_list_pdf(filename, band_name, inputs, outputs):
    """
    Create a PDF with Input List and Output List tables.
    
    Args:
        filename: Output PDF filename
        band_name: Name of the band/act
        inputs: List of dicts with keys: ch, input_name, mic, position, notes
        outputs: List of dicts with keys: aux, destination, location, contents, notes
    """
    doc = SimpleDocTemplate(
        filename, 
        pagesize=landscape(letter),
        rightMargin=36, leftMargin=36,
        topMargin=36, bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title = Paragraph(f"<b>{band_name} - Technical Rider</b>", styles['Heading1'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Input List Header
    elements.append(Paragraph("<b>INPUT LIST</b>", styles['Heading2']))
    
    # Input table data
    input_data = [['Ch', 'Input', 'Mic/DI', 'Position', 'Notes']]
    for inp in inputs:
        input_data.append([
            inp.get('ch', ''),
            inp.get('input_name', ''),
            inp.get('mic', ''),
            inp.get('position', ''),
            inp.get('notes', '')
        ])
    
    input_table = Table(input_data, colWidths=[30, 120, 100, 150, 200])
    input_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    elements.append(input_table)
    elements.append(Spacer(1, 24))
    
    # Output List Header
    elements.append(Paragraph("<b>OUTPUT LIST</b>", styles['Heading2']))
    
    # Output table data
    output_data = [['Output', 'Destination', 'Location', 'Contents', 'Notes']]
    for out in outputs:
        output_data.append([
            out.get('aux', ''),
            out.get('destination', ''),
            out.get('location', ''),
            out.get('contents', ''),
            out.get('notes', '')
        ])
    
    output_table = Table(output_data, colWidths=[60, 100, 150, 150, 140])
    output_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    elements.append(output_table)
    
    doc.build(elements)

# Example usage
inputs = [
    {'ch': '1', 'input_name': 'Kick', 'mic': 'Beta 52', 'position': 'DS Center', 'notes': ''},
    {'ch': '2', 'input_name': 'Vox 1', 'mic': 'SM58', 'position': 'SR', 'notes': 'Split to IEM'},
]

outputs = [
    {'aux': 'Aux 1', 'destination': 'Wedge 1', 'location': 'SR', 'contents': 'Vox1, Vox2', 'notes': 'Vox priority'},
]

# create_input_list_pdf("tech_rider.pdf", "Band Name", inputs, outputs)
```

---

## Cross-Reference

- Use with **Skill 01: Stage Plot Completeness Checklist** to verify list-to-plot consistency
- Use with **Skill 03: IEM and Wedge Monitoring Strategy** for signal flow documentation
- Apply **Skill 02: Stage Plot Graphics Creation** to generate icons for every list item

---

## Common Pitfalls from Run Analysis

### Pitfall: Output Items Not Visualized
**What went wrong:** Wedge 1 and Wedge 2 appeared in the Output List but had no triangle icons on the stage plot.

**The fix:** Before finalizing, scan the Output List and ensure each destination (especially wedges and IEM packs) has a corresponding visual element on the stage diagram.

**Prevention:** Use this code snippet to validate:
```python
# Pseudo-code for validation
def validate_completeness(input_list, output_list, stage_plot):
    input_count = len(input_list)
    output_count = len(output_list)
    
    # Count icons on stage plot
    icons_on_plot = count_visual_elements(stage_plot)
    
    # Each input (mic/DI) should have an icon
    # Each output (wedge/IEM) should have an icon
    expected_icons = input_count + output_count
    
    if icons_on_plot < expected_icons:
        missing = expected_icons - icons_on_plot
        raise ValueError(f"Missing {missing} visual elements on stage plot!")
```

---

## References

- CD Baby: "How to Make a Stage Plot for Your Band"
- Mixing Music Live: "Input Lists and Stage Plots"
- ProSoundWeb: "Simple Yet Vital: Best Practices In Developing Input Lists And Stage Plots"
- This Tour Life: "Creating an Input List"
