type: strategy

# Stage Plot Completeness Verification Checklist

## When to Use
- Creating any stage plot for touring bands or live performances
- Before finalizing venue advance documentation
- When producing input lists and output lists for live sound
- Prior to submitting stage plots to venue production teams
- Quality assurance for A/V tech documentation

## One-Line Summary
Ensure every item listed in input/output documentation appears visually on the stage plot with appropriate icons and labels.

## Main Body

### The Core Completeness Principle
**Every item referenced in technical documentation must have a corresponding visual representation.** This is the #1 failure point in stage plot creation.

### Pre-Submission Checklist

#### 1. Input List Verification
- [ ] Every microphone in the Input List has an icon on stage
- [ ] Every DI box in the Input List has an icon on stage
- [ ] Every line/instrument input has a visual marker
- [ ] Channel numbers on Input List match stage annotations

#### 2. Output List Verification (CRITICAL)
- [ ] **Every monitor wedge listed appears as an icon on stage**
- [ ] **Every IEM system listed appears as an icon or annotation**
- [ ] **Every speaker/amp output has visual placement**
- [ ] Output numbers/labels match between list and diagram

#### 3. Stage Plot Visual Check
- [ ] All musicians positioned correctly (Stage Right/Left from audience perspective)
- [ ] All amplifiers shown with icons
- [ ] All instruments shown with appropriate symbols
- [ ] Monitor wedge placement is physically logical
- [ ] IEM transmitters/belt packs shown if required

#### 4. Cross-Reference Validation
Match these pairs exactly:
| Document Element | Stage Plot Element |
|-----------------|-------------------|
| Input List Item N | Icon + Label N |
| Output List Wedge X | Wedge Icon X |
| Output List IEM Y | IEM Icon/Label Y |
| Microphone List Entry | Mic Icon at position |

### Critical Failure Pattern to Avoid
❌ **Listing items in Output List but not drawing them on stage**

Example of failure:
- Output List says: "Wedge 1 (Vox1), Wedge 2 (Vox2), Wedge 3 (Drums)"
- Stage plot shows: Only Wedge 3 icon drawn
- Result: Venue staff cannot verify placement of Wedge 1 and 2 during load-in

### Verification Workflow
1. Create Input List → Mark each item with [P] (Placed) when drawn on stage
2. Create Output List → Mark each item with [P] when drawn on stage
3. Review stage plot → Verify every [P] item is actually visible
4. Final check: Ask "Can a venue tech set up using ONLY this diagram?"

## Examples

### Example 1: Simple Band Setup
**Scenario**: 4-piece band with 2 vocalists using wedges

**Input List:**
1. Kick Drum Mic
2. Snare Mic
3. OH Left
4. OH Right
5. Bass DI
6. Guitar Amp Mic
7. Vox1 Mic
8. Vox2 Mic

**Output List:**
- Wedge 1 (Vox1)
- Wedge 2 (Vox2)
- Wedge 3 (Drums)

**Visual Verification:**
- ✓ 8 microphone icons on stage (at drum kit, amp, vocal positions)
- ✓ 1 DI box icon at bass position
- ✓ 3 wedge icons placed at appropriate angles
- ✓ Each icon labeled with corresponding number

### Example 2: IEM + Wedge Hybrid Setup
**Scenario**: Band with IEMs for some members, wedges for others

**Input List:** 12 channels including vocal mics with splits

**Output List:**
- IEM 1 (Lead Vox)
- IEM 2 (BV)
- Wedge 1 (Drummer - receives Vox1+Vox2 mix)

**Visual Verification:**
- ✓ All 12 input icons present
- ✓ XLR splitters shown at vocal mic positions (Y-cables or splitter boxes)
- ✓ IEM transmitters shown near vocal positions
- ✓ Wedge 1 shown at drummer's 10 o'clock position
- ✓ Label indicates Wedge 1 receives "Vox1+Vox2 mix"

## Code Demo
N/A - This is a strategy/checklist skill. Use as a manual verification guide before submission.

## Run#1 Failure Analysis
**Original Failure**: The stage plot listed Wedge 1 (Vox1) and Wedge 2 (Vox2) in the Output List but failed to include graphic icons for these wedges on the visual diagram. Only Wedge 3 (Drums) was drawn.

**Root Cause**: Incomplete cross-reference between Output List items and stage plot visualization.

**Prevention**: Use this checklist to verify: `len(output_list_items) == len(wedge_icons_on_plot)`
