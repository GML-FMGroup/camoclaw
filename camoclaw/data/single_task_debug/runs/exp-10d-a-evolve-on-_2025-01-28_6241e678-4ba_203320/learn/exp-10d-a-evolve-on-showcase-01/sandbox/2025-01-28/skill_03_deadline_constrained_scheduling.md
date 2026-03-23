type: strategy

# Deadline-Constrained Schedule Development

## When to Use
- Any project with a fixed, non-negotiable deadline
- Client-mandated delivery dates that cannot be missed
- Contractual deadlines with penalties for late delivery
- Schedules where scope must fit within calendar constraints

## One-Line Summary
Build the schedule backwards from the hard deadline, validating at each step that all tasks fit within available working days.

## Main Body

### The Backward-Scheduling Method

When a deadline is fixed, traditional forward-scheduling often results in overruns. Instead:

#### Step 1: Anchor at the Deadline
```
Final Delivery: Aug 29 (FIXED - cannot move)
```

#### Step 2: Calculate Working Days Backward
```
Available span: July 7 → August 29
Working days available: 40 days (calculated)
```

#### Step 3: List All Required Tasks
Include EVERY task:
- Your team's work
- Client review cycles
- Revision time after feedback
- Buffer for unexpected delays
- Delivery/formatting time

#### Step 4: Sum Task Durations
```
Total task days needed = Sum of all task durations
```

#### Step 5: Validate Fit
```
IF total_task_days > available_working_days:
    → Schedule is IMPOSSIBLE as defined
    → Options:
        1. Reduce scope (eliminate tasks/features)
        2. Compress durations (parallelize, add resources)
        3. Negotiate deadline extension
        4. Reduce revision rounds
ELSE:
    → Schedule is feasible, proceed with assignment
```

### Critical Rule: The Deadline is Sacred

**A schedule that exceeds the deadline is professionally unusable.**
- Missing deadlines risks contract breach
- Client cannot use schedule for planning
- Department heads cannot rely on dates
- Project may be cancelled or penalized

### Task Duration Estimation Best Practices

#### Be Realistic, Not Optimistic
- Use historical data if available
- Account for handoff delays between tasks
- Include buffer time (10-15% is standard)

#### Client Review Cycles
**Common Pattern:**
```
Deliver asset → Client review → Receive feedback → Implement revisions
     1 day    →    2-3 days    →     1 day      →     2-3 days
```

**Minimum client review time:** 2 working days
**Minimum revision time:** Equal to original task time or 50%, whichever is greater

#### Parallel vs. Sequential Tasks
**Sequential:** One must finish before next starts (dependencies)
```
Script → Storyboard → Pre-prod → Shoot → Edit
```

**Parallel:** Can happen simultaneously (adds no days to critical path)
```
Script writing
Graphic design (of UI elements)
Location scouting
```

### The Validation Checkpoints

#### Checkpoint 1: After Task Listing
```
□ All required tasks documented?
□ Client review cycles included?
□ Revision rounds counted?
□ Buffer time added?
```

#### Checkpoint 2: After Duration Estimation
```
□ Sum of sequential tasks calculated?
□ Parallel tasks identified and optimized?
□ Critical path determined?
□ Total duration ≤ available working days?
```

#### Checkpoint 3: Before Finalizing
```
□ Each task has assigned start and end date?
□ Client review dates clearly marked?
□ Final delivery date matches hard deadline?
□ Schedule reviewed by another person?
```

## Examples

### Example 1: Backward Scheduling from Deadline
**Scenario:** Final delivery must be Aug 29. Work backward:

```
Aug 29 (Fri) - Final Delivery
Aug 28 (Thu) - Format/Export/Upload (1 day)
Aug 25-27 (Mon-Wed) - Final Polish/Color/Sound (3 days)
Aug 21-22 (Thu-Fri) - Client Final Approval* (2 days)
Aug 18-20 (Mon-Wed) - Revision Round 3 (3 days)
Aug 15 (Fri) - Client Feedback on V2* (1 day buffer start)
...
Continue backward to Jul 7
```

### Example 2: Validation Failure (Run#1 Scenario)
**Available:** 40 working days (Jul 7 - Aug 29)

**Task List (Sequential):**
```
Pre-production:     12 days
Production (shoot):  1 day  
Post-production:    25 days
Client reviews:      8 days
Revisions:          10 days
--------------------------
Total:              56 days
```

**Result:** 56 > 40 → Schedule exceeds deadline by 16 days → **UNACCEPTABLE**

**Solutions:**
1. Reduce revisions from 3 rounds to 1 (save 7 days)
2. Compress post-prod from 25 to 18 days (add resources)
3. Negotiate extension to Sep 12 (add 10 working days)

### Example 3: Parallel Task Optimization
**Sequential approach:**
```
Script (5 days) → Storyboard (5 days) → Graphics (5 days) = 15 days
```

**Parallel optimization:**
```
Week 1: Script (5 days)
        ↓ AND Graphics start (can begin with script outline)
Week 2: Storyboard (5 days) 
        ↓ AND Graphics continue
Week 3: Graphics complete (overlapped with storyboard)
Total: 10 days (saved 5 days through parallelization)
```

## Code Demo

### Python: Backward Schedule Validation
```python
from datetime import datetime, timedelta

def validate_deadline_schedule(deadline, tasks, buffer_days=2):
    """
    Validate if tasks fit within deadline working backward.
    
    Args:
        deadline: datetime.date - Hard deadline (cannot move)
        tasks: list of (task_name, duration, is_client_task)
        buffer_days: int - Buffer before deadline
    
    Returns:
        dict with validation results
    """
    # Work backward from deadline
    current_end = deadline - timedelta(days=buffer_days)
    schedule = []
    total_days = 0
    
    # Process tasks in reverse order
    for task_name, duration, is_client in reversed(tasks):
        # Calculate start (working backward)
        current_start = current_end
        days_to_subtract = duration - 1
        
        while days_to_subtract > 0:
            current_start -= timedelta(days=1)
            if current_start.weekday() < 5:  # Mon-Fri
                days_to_subtract -= 1
        
        schedule.append({
            'task': task_name,
            'start': current_start,
            'end': current_end,
            'duration': duration,
            'is_client': is_client
        })
        
        total_days += duration
        current_end = current_start - timedelta(days=1)
        
        # Skip weekends
        while current_end.weekday() >= 5:
            current_end -= timedelta(days=1)
    
    required_start = schedule[-1]['start']
    
    return {
        'is_valid': True,  # Would compare against known start date
        'required_start': required_start,
        'total_task_days': total_days,
        'schedule': list(reversed(schedule))
    }

# Example usage
deadline = datetime(2025, 8, 29).date()
tasks = [
    ("Final Delivery", 1, False),
    ("Export/Upload", 1, False),
    ("Final Polish", 2, False),
    ("Client Approval", 2, True),
    ("Revisions", 3, False),
]

result = validate_deadline_schedule(deadline, tasks)
print(f"Must start by: {result['required_start']}")
print(f"Total days: {result['total_task_days']}")
```

## Key Takeaways

1. **Backward scheduling** from fixed deadlines prevents overruns
2. **Validate early:** Check task sum against available days before detailed planning
3. **Client reviews are critical path** - include realistic timeframes
4. **Parallel tasks** can compress schedule without cutting quality
5. **Buffer time** is essential - never plan to use 100% of available time
6. **If tasks > available days, negotiate scope or deadline** - don't submit an impossible schedule
