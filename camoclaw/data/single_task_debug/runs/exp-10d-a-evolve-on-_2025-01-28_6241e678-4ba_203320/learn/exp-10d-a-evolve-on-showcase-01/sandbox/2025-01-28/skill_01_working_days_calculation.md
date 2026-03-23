type: technical

# Working Days Calculation for Production Schedules

## When to Use
- Any project scheduling task with fixed start and end dates
- When the deliverable requires fitting tasks within a specific calendar window
- Video/film production schedules with client-mandated deadlines
- Any schedule where "working days" means Monday-Friday only (excluding weekends)

## One-Line Summary
Always calculate the actual number of working days between dates excluding weekends before building a schedule.

## Main Body

### The Critical Rule
**NEVER assume calendar days equal working days.** A 54-day calendar span typically contains only 38-40 working days (Monday-Friday).

### Step-by-Step Process

1. **Identify Hard Constraints**
   - Start date (kickoff/deadline): Date X
   - End date (delivery deadline): Date Y
   - These are FIXED and immovable

2. **Calculate Available Working Days**
   ```
   - Count Monday through Friday only
   - Exclude Saturdays and Sundays
   - Include both start and end dates if they fall on weekdays
   - Result = Maximum working days available for the schedule
   ```

3. **Validate Task Duration Sum**
   - Sum all task durations in working days
   - If sum > available working days → CRITICAL ERROR
   - Must reduce scope, add resources, or negotiate deadline

4. **Common Pitfall: The "Day X" Trap**
   - AVOID labeling with "Day 0, Day 5, Day 10..."
   - ALWAYS use actual calendar dates (e.g., "Jul 7, Jul 14, Jul 21...")
   - Calendar dates are immediately actionable by stakeholders

### Industry Standard Working Week
- Working days: Monday, Tuesday, Wednesday, Thursday, Friday
- Weekend days: Saturday, Sunday (non-working)
- No work occurs on weekends unless explicitly scheduled as overtime

## Examples

### Example 1: Simple Duration Check
**Scenario:** Project runs from Monday, July 7, 2025 to Friday, August 29, 2025

**Calculation:**
- July 7 to August 29 = 54 calendar days
- Working days = 40 days (Monday-Friday only)

**Mistake to Avoid:**
- Claiming "52 working days available" when only 40 exist
- This causes a 12-day overage that makes schedule unusable

### Example 2: Task Fitting Verification
**Scenario:** 8 tasks with durations: 5 + 3 + 7 + 4 + 6 + 5 + 8 + 3 = 41 working days

**Available:** 40 working days between kickoff and deadline

**Result:** Schedule is OVER by 1 working day → Must eliminate 1 day of work

### Example 3: Calendar Date Labeling
**WRONG (Abstract):**
```
Day 0: Kickoff
Day 5: Script complete
Day 12: Storyboard review
```

**CORRECT (Calendar dates):**
```
Mon Jul 7: Kickoff
Mon Jul 14: Script complete  
Wed Jul 23: Storyboard review
```

## Code Demo

### Python: Calculate Working Days Between Dates
```python
from datetime import datetime, timedelta

def count_working_days(start_date, end_date):
    """
    Calculate working days (Mon-Fri) between two dates (inclusive).
    
    Args:
        start_date: datetime.date or datetime.datetime
        end_date: datetime.date or datetime.datetime
    
    Returns:
        int: Number of working days
    """
    working_days = 0
    current = start_date
    
    while current <= end_date:
        # weekday(): Monday=0, Sunday=6
        if current.weekday() < 5:  # 0-4 are Mon-Fri
            working_days += 1
        current += timedelta(days=1)
    
    return working_days

# Example usage
def validate_schedule(kickoff_date, deadline_date, total_task_days):
    """
    Validates if tasks fit within deadline.
    Returns (is_valid, available_days, overflow)
    """
    available = count_working_days(kickoff_date, deadline_date)
    is_valid = total_task_days <= available
    overflow = max(0, total_task_days - available)
    
    return is_valid, available, overflow

# Real example from Run#1 failure
start = datetime(2025, 7, 7).date()
end = datetime(2025, 8, 29).date()
total_work = 52  # claimed working days

is_valid, available, overflow = validate_schedule(start, end, total_work)
print(f"Available working days: {available}")  # 40
print(f"Task days requested: {total_work}")    # 52
print(f"Overflow: {overflow} days")            # 12 days over!
```

### Python: Generate Calendar Date Labels
```python
def generate_date_labels(start_date, task_durations):
    """
    Generate calendar date labels for tasks.
    
    Args:
        start_date: datetime.date - Project start date
        task_durations: list of (task_name, duration_in_days)
    
    Returns:
        list of (task_name, start_date, end_date)
    """
    results = []
    current = start_date
    
    for task_name, duration in task_durations:
        # Find start date (skip weekends if needed)
        while current.weekday() >= 5:  # Skip Sat/Sun
            current += timedelta(days=1)
        
        start = current
        
        # Calculate end date (count only working days)
        days_counted = 0
        end = start
        while days_counted < duration - 1:
            end += timedelta(days=1)
            if end.weekday() < 5:
                days_counted += 1
        
        results.append((task_name, start, end))
        current = end + timedelta(days=1)
    
    return results

# Example
kickoff = datetime(2025, 7, 7).date()
tasks = [
    ("Concept Development", 5),
    ("Script Writing", 5),
    ("Client Review", 2),
]

labels = generate_date_labels(kickoff, tasks)
for task, start, end in labels:
    print(f"{task}: {start.strftime('%a %b %d')} - {end.strftime('%a %b %d')}")
```

## Key Takeaways

1. **Validate FIRST:** Always calculate available working days BEFORE building the schedule
2. **Calendar Dates:** Use actual dates ("Jul 7") not abstract labels ("Day 0")
3. **Overflow Check:** If tasks exceed available days, the schedule is professionally unusable
4. **Client Deadline is Sacred:** Missing a hard deadline by even 1 day is a contract risk
