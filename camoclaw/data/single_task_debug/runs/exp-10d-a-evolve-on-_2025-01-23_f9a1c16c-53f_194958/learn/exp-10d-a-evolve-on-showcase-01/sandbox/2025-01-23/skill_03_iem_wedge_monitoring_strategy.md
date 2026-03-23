# Skill: IEM and Wedge Monitoring Strategy for Touring Bands

**type:** strategy

---

## When to Use

- When a touring band includes members using IEM (in-ear monitor) systems
- When vocalists need both IEM feeds AND stage wedge monitoring simultaneously
- When some band members use IEM while others use traditional wedge monitors
- When advancing shows requiring split signals (FOH + monitor system splits)
- When creating output lists that must specify routing for each signal path

---

## One-Line Summary

Map every audio path from input through splitting to both IEM and wedge destinations, ensuring all output assignments are visually represented on the stage plot.

---

## Main Body

### Core Strategy: Dual-Path Audio Architecture

Touring bands often require a **dual-path audio architecture** where signals split to serve multiple monitoring systems simultaneously. This requires careful documentation on both input and output lists, plus visual representation on the stage plot.

### IEM + Wedge Hybrid Setup Rules

#### 1. Signal Splitting Configuration

**For each vocal mic requiring IEM:**
- **XLR Split required**: 1 female XLR input → 2 male XLR outputs
- **Path A**: To FOH console
- **Path B**: To IEM transmitter/mixer
- **Output entry**: List BOTH destinations in Output List

**Example Output Entry:**
| Output # | Signal Source | Destination | Notes |
|----------|--------------|-------------|-------|
| 1 | Vox1 Mic | FOH Input 1 / IEM Tx A | Split via mic splitter box |
| 2 | Vox2 Mic | FOH Input 2 / IEM Tx B | Split via mic splitter box |

#### 2. Vocalist Wedge Requirements (IEM users who also want wedges)

Vocalists using IEM systems may still want their own vocals in stage wedges for "feel" or backup:

| Scenario | Wedge Content | Placement |
|----------|--------------|-----------|
| Standard | Vox own voice only | Front of vocalist |
| Enhanced | Vox + blend of band | Front of vocalist |
| Backup only | Triggered if IEM fails | Front of vocalist |

**Critical**: Even when a vocalist primarily uses IEM, if they request wedge presence, the wedge MUST appear on the stage plot AND in the output list.

#### 3. Drummer Wedge Special Considerations

Drummers typically do NOT use IEM and require wedges for all monitor needs:

**Standard Drummer Wedge Setup:**
- Position: 10-11 o'clock position (relative to drummer facing audience)
- Height: Elevated to ear level when seated
- Content: Mix of vocals, click, and key instruments

**Multi-Vocal Drummer:**
If drummer sings, their vocal mic splits:
- Path A: FOH
- Path B: Drummer's wedge

**Drummer Hearing Other Vocalists:**
Include other vocal mics in drummer's wedge mix:
| Wedge # | For Performer | Signal Sources |
|---------|--------------|----------------|
| Wedge X | Drummer | Drummer Vox + Vox1 + Vox2 + instruments |

#### 4. Non-IEM Band Members

For members not using IEM, create dedicated wedge channels:

| Band Member | Wedge Needed | Content |
|-------------|-------------|---------|
| Guitarist (no vox) | Yes | Guitar amp + rhythm support |
| Bassist (no vox, speech only) | Yes | Bass + bass DI + minimal fill |
| Keyboardist | Maybe | Keys + click + vocals |

---

### Output List Structure for IEM + Wedge Tours

#### Section A: IEM Outputs (Wireless Transmitters)
| Output | Type | Signal | Assigned To |
|--------|------|--------|-------------|
| IEM 1 | Wireless Tx | Stereo mix | Vocalist 1 |
| IEM 2 | Wireless Tx | Stereo mix | Vocalist 2 |

#### Section B: Wedge Outputs (Stage Monitors)
| Output | Type | Signal | Placement |
|--------|------|--------|-----------|
| Wedge 1 | Passive | Vox1 IEM + Vox1 backup | Vox1 position |
| Wedge 2 | Passive | Vox2 IEM + Vox2 backup | Vox2 position |
| Wedge 3 | Passive | Drummer mix | 10 o'clock drummer |
| Wedge 4 | Passive | Guitar mix | Guitar position |
| Wedge 5 | Passive | Bass mix | Bass position |

**IMPORTANT**: Every output number above must correspond to a visual icon on the stage plot.

---

### Stage Plot Visual Requirements

#### Mandatory Icons for IEM Systems:
1. **IEM Bodypack icons**: Small rectangle on each IEM user's hip/position
2. **IEM Antenna icons**: Positioned near center stage or SR/SL
3. **Splitter box**: Positioned near drum riser or center

#### Mandatory Icons for Wedge Systems:
1. **Wedge icons**: Triangle shape with output number labeled
2. **Wedge positions**: Aligned with performer's front-of-position
3. **Wedge aiming**: Indicate horn direction with small arrow

---

## Examples

### Example 1: 2 Vocalists (IEM) + 3 Musicians (Wedges) Setup

**Band Configuration:**
- Vox1: IEM primary, wedge backup (vocal in wedge)
- Vox2: IEM primary, wedge backup (vocal in wedge)
- Drummer: No IEM, wedge at 10 o'clock
- Guitarist: No IEM, wedge for guitar
- Bassist: No IEM, wedge for bass fill

**Input List Entries:**
| Ch | Input | Mic/DI | Notes |
|----|-------|--------|-------|
| 1 | Vox1 | Wireless handheld | Split to FOH + IEM |
| 2 | Vox2 | Wireless handheld | Split to FOH + IEM |
| 3 | Drummer vox | SM58 | To drummer wedge |
| 4 | Kick | Beta 52 | |
| 5 | Snare | SM57 | |
| 6 | Bass DI | Passive DI | |
| 7 | Accordion DI | Passive DI | |
| 8 | Acoustic DI | Passive DI | |

**Output List Entries:**
| Output | Signal | Destination | Notes |
|--------|--------|-------------|-------|
| 1 | Vox1 mic | IEM Tx A / FOH Ch1 | Split signal |
| 2 | Vox2 mic | IEM Tx B / FOH Ch2 | Split signal |
| 3 | Drummer vox | Wedge 3 | 10 o'clock position |
| 4 | Vox1 (fill) | Wedge 1 | Front of Vox1 |
| 5 | Vox2 (fill) | Wedge 2 | Front of Vox2 |
| 6 | Guitar amp | Wedge 4 | Front of guitarist |
| 7 | Bass DI | Wedge 5 | Front of bassist |

**Stage Plot Visual Elements:**
- Vox1 position: IEM bodypack icon + Wedge 1 icon
- Vox2 position: IEM bodypack icon + Wedge 2 icon
- Drummer position: Wedge 3 icon at 10 o'clock
- Guitarist position: Guitar amp icon + Wedge 4 icon
- Bassist position: Bass amp icon + Wedge 5 icon

### Example 2: Signal Flow for Vocal Mic Split

**Physical Routing:**
```
Vocal Mic (SM58)
    ↓
Mic Splitter Box (1xF → 2xM XLR)
    ↓                    ↓
FOH Console Ch1      IEM Transmitter A
    ↓                    ↓
House Mix            Vocalist's IEM pack
    ↓
[Recording feed optional]
```

**Stage Plot Icons Required:**
- Microphone icon at vocalist position (labeled "Vox1")
- IEM bodypack icon at vocalist's hip position (labeled "IEM A")
- Wedge icon at front of vocalist position (labeled "Wedge 1")
- Optional: Splitter box icon near drum riser

---

## Code Demo

### Python: Generating IEM + Wedge Output List Structure

```python
import pandas as pd

def create_iem_wedge_output_list(band_config):
    """
    Generate output list for IEM + wedge hybrid setup.
    
    Args:
        band_config: List of dicts with keys:
            - name: Performer name
            - position: Stage position
            - iem: True/False
            - wedge: True/False
            - wedge_content: List of signals
    
    Returns:
        DataFrame with complete output list
    """
    outputs = []
    iem_count = 0
    wedge_count = 0
    
    for member in band_config:
        # IEM output
        if member.get('iem'):
            iem_count += 1
            outputs.append({
                'Output #': f"IEM {iem_count}",
                'Type': 'Wireless TX',
                'Signal': f"{member['name']} IEM Mix",
                'Destination': f"{member['name']} Bodypack",
                'Location': member['position'],
                'Visual_Required': True
            })
        
        # Wedge output
        if member.get('wedge'):
            wedge_count += 1
            content = ', '.join(member.get('wedge_content', [member['name']]))
            outputs.append({
                'Output #': f"Wedge {wedge_count}",
                'Type': 'Stage Monitor',
                'Signal': content,
                'Destination': f"{member['name']} Wedge",
                'Location': member['position'],
                'Visual_Required': True
            })
    
    df = pd.DataFrame(outputs)
    
    # Validate: Every output must have visual representation
    missing_visuals = df[df['Visual_Required'] == False]
    if not missing_visuals.empty:
        print("WARNING: Outputs missing visual representation!")
        print(missing_visuals)
    
    return df

# Example usage
band = [
    {'name': 'Vox1', 'position': 'Stage Right', 'iem': True, 'wedge': True, 'wedge_content': ['Vox1']},
    {'name': 'Vox2', 'position': 'Stage Left', 'iem': True, 'wedge': True, 'wedge_content': ['Vox2']},
    {'name': 'Drummer', 'position': 'Center Rear', 'iem': False, 'wedge': True, 'wedge_content': ['Drums', 'Vox1', 'Vox2']},
]

output_df = create_iem_wedge_output_list(band)
print(output_df.to_string(index=False))
```

### Validation Checklist for IEM + Wedge Tours

```python
def validate_iem_wedge_stage_plot(output_list, stage_plot_elements):
    """
    Verify every output has corresponding visual on stage plot.
    
    Args:
        output_list: DataFrame with Output # column
        stage_plot_elements: List of dicts with 'type' and 'label' keys
    """
    errors = []
    
    # Get all outputs that should have visuals
    visual_outputs = output_list[output_list['Type'].isin(['Wireless TX', 'Stage Monitor'])]
    
    for _, output in visual_outputs.iterrows():
        output_num = output['Output #']
        
        # Check if this output appears on stage plot
        found = any(
            element.get('label', '').startswith(output_num.split()[0]) 
            and output_num.split()[-1] in element.get('label', '')
            for element in stage_plot_elements
        )
        
        if not found:
            errors.append(f"CRITICAL: {output_num} ({output['Type']}) listed in outputs but missing from stage plot!")
    
    if errors:
        print("\n".join(errors))
        return False
    else:
        print("✓ All outputs have corresponding stage plot visuals")
        return True
```

---

## Key Takeaways

1. **Every split signal creates multiple outputs**: Document all paths
2. **IEM users may still need wedges**: Always confirm wedge requirements
3. **Visual completeness is mandatory**: Output list items must match stage plot icons 1:1
4. **Drummer wedges are multi-source**: Include all vocalist feeds they need to hear
5. **Splitter placement matters**: Position near center for cable management efficiency