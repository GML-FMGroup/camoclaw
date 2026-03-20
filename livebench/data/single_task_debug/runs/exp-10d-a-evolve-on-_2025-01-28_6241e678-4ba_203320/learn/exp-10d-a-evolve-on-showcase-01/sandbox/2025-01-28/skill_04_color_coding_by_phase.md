type: strategy

# Skill: Color-Coding Production Schedule by Phase and Stakeholder

## When to Use
- Creating visual production schedules with multiple phases (pre-production, production, post-production)
- Need to distinguish between internal team tasks and external stakeholder tasks
- Building Gantt charts or calendar views that require quick visual scanning
- Delivering schedules to department heads who need immediate visual cues
- Any project where phase identification and role clarity are critical

## One-Line Summary
Use consistent color coding for production phases and distinct accent colors for client/stakeholder tasks to create immediately scannable, professional schedules.

## Main Body

### Phase-Based Color Coding Standards

| Phase | Recommended Color | Hex Code | Rationale |
|-------|-------------------|----------|-----------|
| Planning/Strategy | Blue | #4A90D9 | Represents thoughtfulness, trust, analysis |
| Pre-Production | Pink/Magenta | #E91E63 | Distinct creative planning phase |
| Production/Shoot | Red/Orange | #FF5722 | High energy, critical execution |
| Post-Production | Green | #4CAF50 | Growth, refinement, completion |
| Graphics/Design | Yellow/Gold | #FFC107 | Creative visual work |
| Delivery/Distribution | Purple | #9C27B0 | Final stage, sophistication |

### Stakeholder Task Color Coding

| Task Type | Recommended Color | Hex Code | Marking |
|-----------|-------------------|----------|---------|
| Internal Team Tasks | Use phase color | As above | None |
| Client/External Tasks | Cyan/Light Blue | #00BCD4 | Asterisk (*) or "CLIENT" prefix |
| Review/Approval Points | Light Cyan | #B2EBF2 | Clock icon or "REVIEW" label |
| Milestones/Deadlines | Dark Gray/Black | #424242 | Diamond shape or bold text |

### Color Application Rules

1. **Consistency**: Same phase = same color throughout the entire document
2. **Contrast**: Ensure text remains readable on colored backgrounds
3. **Accessibility**: Use patterns or labels in addition to color for colorblind stakeholders
4. **Print-Friendly**: Test that colors are distinguishable in grayscale
5. **Client Distinction**: Always differentiate client tasks with both color AND label

### Visual Hierarchy Best Practices

- **Primary**: Phase colors fill task bars/rows
- **Secondary**: Stakeholder colors as borders or highlights
- **Tertiary**: Milestone markers as distinct icons

## Examples

### Example 1: Basic Color Coding
```
Task                    | Duration | Color
------------------------|----------|-------
Script Writing          | 5 days   | Pink (Pre-Production)
Client Script Review*   | 2 days   | Cyan (Client Task)
Location Scouting       | 3 days   | Pink (Pre-Production)
Shoot Day               | 1 day    | Orange (Production)
Rough Cut Edit          | 5 days   | Green (Post-Production)
Client Review v1*       | 3 days   | Cyan (Client Task)
Final Delivery          | 1 day    | Purple (Delivery)
```

### Example 2: Gantt Chart Color Application
```
Phase: Pre-Production (Pink #E91E63)
[████████████████] Script Development  [Jul 8-12]
[------]          Client Review*        [Jul 13-14]  (Cyan #00BCD4)
[████████]        Storyboarding         [Jul 15-18]  (Pink)

Phase: Production (Orange #FF5722)
[█]               Shoot Day             [Jul 22]     (Orange)

Phase: Post-Production (Green #4CAF50)
[████████████████] Rough Cut            [Jul 23-29]  (Green)
[------]          Client Review v1*     [Jul 30-Aug 1] (Cyan)
```

## Code Demo

```python
# Python with openpyxl for color-coded Excel schedules
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter

# Define color palette
PHASE_COLORS = {
    'pre_production': 'FFE91E63',    # Pink
    'production': 'FFFF5722',         # Orange
    'post_production': 'FF4CAF50',    # Green
    'graphics': 'FFFFC107',           # Yellow
    'client_task': 'FF00BCD4',        # Cyan
    'delivery': 'FF9C27B0'            # Purple
}

def apply_phase_coloring(ws, row, phase, is_client_task=False):
    """
    Apply color coding to a schedule row based on phase and stakeholder.
    
    Args:
        ws: openpyxl worksheet
        row: row number to color
        phase: one of PHASE_COLORS keys
        is_client_task: True if this is a client/external task
    """
    if is_client_task:
        fill_color = PHASE_COLORS['client_task']
        font_color = '000000'  # Black text on cyan
    else:
        fill_color = PHASE_COLORS.get(phase, 'FFFFFFFF')
        font_color = 'FFFFFF' if phase in ['pre_production', 'production'] else '000000'
    
    fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type='solid')
    font = Font(color=font_color, bold=is_client_task)
    
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = fill
        cell.font = font
        
        if is_client_task and col == 1:  # Task name column
            cell.value = f"{cell.value} *"

# Usage example
wb = Workbook()
ws = wb.active
ws.title = "Production Schedule"

# Add tasks with color coding
tasks = [
    ("Script Development", 'pre_production', False),
    ("Client Script Review", 'client_task', True),
    ("Storyboarding", 'pre_production', False),
    ("Shoot Day", 'production', False),
    ("Rough Cut Edit", 'post_production', False),
    ("Client Review v1", 'client_task', True),
]

for idx, (task, phase, is_client) in enumerate(tasks, start=2):
    ws.cell(row=idx, column=1, value=task)
    apply_phase_coloring(ws, idx, phase, is_client)

wb.save('/tmp/color_coded_schedule.xlsx')
print("ARTIFACT_PATH:/tmp/color_coded_schedule.xlsx")
```

## Common Pitfalls to Avoid

1. **Inconsistent Color Assignment**: Don't switch phase colors mid-document
2. **Too Many Colors**: Limit to 5-7 distinct colors maximum
3. **Poor Contrast**: Always ensure text is readable on colored backgrounds
4. **Missing Client Distinction**: Client tasks must be visually distinct, not just labeled
5. **Color-Only Information**: Include text labels for accessibility

## Quality Checklist

Before submitting a color-coded schedule, verify:
- [ ] Each phase has a unique, consistent color
- [ ] All client/external tasks use the designated stakeholder color
- [ ] Text is readable on all colored backgrounds
- [ ] Colors are distinguishable in grayscale (print preview)
- [ ] Legend/key is included explaining color meanings
- [ ] No more than 7 colors are used
- [ ] Client tasks are marked with asterisk or explicit label
