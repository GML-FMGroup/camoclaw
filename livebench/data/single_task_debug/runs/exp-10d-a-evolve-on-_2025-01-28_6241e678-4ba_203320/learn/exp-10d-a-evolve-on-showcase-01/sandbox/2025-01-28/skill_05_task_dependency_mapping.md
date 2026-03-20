# Skill: Task Dependency Mapping for Production Schedules

type: technical

---

## When to Use

- Any production schedule with tasks that have prerequisite relationships (e.g., editing cannot start until shoot is complete)
- Multi-phase projects where downstream work depends on upstream deliverables
- Client review workflows where approval gates control progression
- Parallel workstreams that must synchronize at specific milestones
- Any schedule requiring critical path analysis

---

## One-Line Summary

Explicitly map and validate all task dependencies to ensure logical workflow sequencing and identify the critical path.

---

## Main Body

### The Dependency Problem

Schedules fail when dependencies are implicit or ignored. A schedule that assumes "editing starts after shooting" but places them on the same day is logically invalid and unexecutable.

### Types of Dependencies

| Dependency Type | Description | Example |
|----------------|-------------|---------|
| **Finish-to-Start (FS)** | Task B cannot start until Task A finishes | Editing cannot start until shoot wraps |
| **Start-to-Start (SS)** | Task B starts when Task A starts | Sound design starts when editing starts |
| **Finish-to-Finish (FF)** | Task B finishes when Task A finishes | Graphics must finish by final edit deadline |
| **Client Approval Gate** | Work cannot proceed without client sign-off | Round 2 editing waits for Round 1 approval |

### Dependency Mapping Checklist

1. **List all tasks** with their durations
2. **Identify prerequisites** for each task (what must finish first)
3. **Identify successors** for each task (what comes after)
4. **Flag client approval dependencies** explicitly
5. **Calculate earliest start date** for each task based on predecessor finish dates
6. **Validate no circular dependencies** exist
7. **Identify the critical path** (longest dependency chain)

### Common Dependency Errors

- **Missing finish-to-start links**: Assuming work can overlap when it cannot
- **Ignoring approval gates**: Not accounting for client review time
- **Implicit dependencies**: Assuming "everyone knows" the order
- **Resource conflicts**: Same team assigned to simultaneous dependent tasks

### Parallel vs. Sequential Work

**Can run parallel:**
- Sound design and color grading (different teams)
- Script writing and initial location scouting (different resources)

**Must be sequential:**
- Script approval → Storyboard creation
- Shoot → Rough edit
- Client approval Round N → Round N+1 editing

---

## Examples

### Example 1: Simple Linear Chain
```
Kickoff (Day 1) → Script Writing (Days 2-6) → Storyboard (Days 7-11) → Shoot (Day 12)
```

### Example 2: Parallel Workstreams with Synchronization
```
Script Writing (Days 2-6)
       ↓
Storyboard (Days 7-11) ──┐
                         ├──→ SHOOT (Day 16) ←── Location Scout (Days 7-14)
Casting (Days 7-12) ─────┘
```

### Example 3: Client Review Workflow
```
Rough Edit (Days 1-5) → Client Review* (Days 6-7) → Revise Round 1 (Days 8-9)
                                                             ↓
                    Client Approval* (Day 10) → Final Delivery
```

*Client tasks shown with asterisk per deliverable requirements

---

## Code Demo

```python
from datetime import datetime, timedelta
from collections import defaultdict

def calculate_schedule_with_dependencies(tasks, dependencies, start_date, holidays=None):
    """
    Calculate task start/end dates respecting dependencies.
    
    Args:
        tasks: Dict[task_name, duration_in_days]
        dependencies: Dict[task_name, list of prerequisite task names]
        start_date: Project start date (datetime)
        holidays: List of holiday dates (optional)
    
    Returns:
        Dict[task_name, {'start': date, 'end': date, 'duration': int}]
    """
    if holidays is None:
        holidays = []
    
    def add_working_days(start, days):
        """Add N working days to a date, skipping weekends and holidays."""
        current = start
        added = 0
        while added < days:
            current += timedelta(days=1)
            if current.weekday() < 5 and current not in holidays:
                added += 1
        return current
    
    # Topological sort for dependency order
    def topo_sort(tasks, deps):
        in_degree = {t: 0 for t in tasks}
        for prereqs in deps.values():
            for p in prereqs:
                if p in in_degree:
                    in_degree[p] += 1
        
        queue = [t for t in tasks if in_degree[t] == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for task, prereqs in deps.items():
                if node in prereqs:
                    in_degree[task] -= 1
                    if in_degree[task] == 0:
                        queue.append(task)
        return result
    
    schedule = {}
    sorted_tasks = topo_sort(tasks, dependencies)
    
    for task in sorted_tasks:
        prereqs = dependencies.get(task, [])
        if prereqs:
            # Start after latest prerequisite finishes
            earliest_start = max(schedule[p]['end'] for p in prereqs if p in schedule)
            start = earliest_start + timedelta(days=1)
        else:
            start = start_date
        
        end = add_working_days(start, tasks[task])
        schedule[task] = {
            'start': start,
            'end': end,
            'duration': tasks[task]
        }
    
    return schedule

# Example usage
tasks = {
    'Kickoff': 0,
    'Script Writing': 5,
    'Storyboard': 5,
    'Location Scout': 5,
    'Casting': 4,
    'Shoot': 1,
    'Rough Edit': 5,
    'Client Review 1': 2,
    'Revise Round 1': 2,
}

dependencies = {
    'Script Writing': ['Kickoff'],
    'Storyboard': ['Script Writing'],
    'Location Scout': ['Script Writing'],
    'Casting': ['Script Writing'],
    'Shoot': ['Storyboard', 'Location Scout', 'Casting'],
    'Rough Edit': ['Shoot'],
    'Client Review 1': ['Rough Edit'],
    'Revise Round 1': ['Client Review 1'],
}

start = datetime(2025, 7, 7)
schedule = calculate_schedule_with_dependencies(tasks, dependencies, start)

# Print schedule
for task, dates in schedule.items():
    print(f"{task}: {dates['start'].strftime('%b %d')} - {dates['end'].strftime('%b %d')}")
```

---

## Key Takeaways

1. **Always make dependencies explicit** - document what must finish before what
2. **Client approvals are dependencies** - treat them as gates, not parallel tasks
3. **Calculate from dependencies, not arbitrary dates** - start dates derive from predecessor end dates
4. **Watch for resource conflicts** - dependencies aren't just logical, they're also about who does the work
5. **The critical path determines timeline** - the longest dependency chain sets the minimum project duration

---

## Validation Checklist

Before finalizing any schedule:
- [ ] Every task has its prerequisites documented
- [ ] No task starts before its prerequisites finish
- [ ] Client review tasks have adequate duration (never < 2 days)
- [ ] Critical path is identified and validated against deadline
- [ ] Parallel tasks don't share the same resource
- [ ] Review cycles account for client availability
