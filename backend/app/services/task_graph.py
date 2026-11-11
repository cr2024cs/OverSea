from collections import deque


def build_edges(tasks):
    codes = {task["code"] for task in tasks}
    edges = []
    for task in tasks:
        for predecessor in task["predecessors"]:
            if predecessor in codes:
                edges.append({"source": predecessor, "target": task["code"]})
    return edges


def compute_schedule(tasks):
    """按任务时长计算最早开始、总工期与关键路径。"""
    by_code = {task["code"]: task for task in tasks}
    indegree = {code: 0 for code in by_code}
    adjacency = {code: [] for code in by_code}

    for code, task in by_code.items():
        for predecessor in task["predecessors"]:
            if predecessor in by_code:
                adjacency[predecessor].append(code)
                indegree[code] += 1

    ready = deque(sorted(code for code, degree in indegree.items() if degree == 0))
    order = []
    while ready:
        code = ready.popleft()
        order.append(code)
        for target in sorted(adjacency[code]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)

    if len(order) != len(by_code):
        raise ValueError("任务依赖存在循环，无法计算关键路径。")

    earliest_start = {}
    earliest_finish = {}
    for code in order:
        task = by_code[code]
        predecessors = [p for p in task["predecessors"] if p in by_code]
        start = max((earliest_finish[p] for p in predecessors), default=0)
        earliest_start[code] = start
        earliest_finish[code] = start + task["duration_days"]

    longest = {}
    previous = {}
    for code in order:
        task = by_code[code]
        predecessors = [p for p in task["predecessors"] if p in by_code]
        if not predecessors:
            longest[code] = task["duration_days"]
            previous[code] = None
        else:
            best = max(predecessors, key=lambda item: longest[item])
            longest[code] = longest[best] + task["duration_days"]
            previous[code] = best

    end_code = max(longest, key=longest.get)
    critical_path = []
    cursor = end_code
    while cursor is not None:
        critical_path.append(cursor)
        cursor = previous[cursor]
    critical_path.reverse()

    return {
        "order": order,
        "earliest_start": earliest_start,
        "total_days": longest[end_code],
        "critical_path": critical_path,
    }


def snapshot(tasks, critical_path):
    return {
        "codes": {
            task["code"]: {
                "name": task["name"],
                "predecessors": sorted(task["predecessors"]),
            }
            for task in tasks
        },
        "critical_path": critical_path,
    }


def diff_snapshots(previous, current):
    if not previous or not previous.get("codes"):
        return {"first_generation": True, "added": [], "removed": [], "changed": []}

    old_codes = previous.get("codes", {})
    new_codes = current.get("codes", {})
    added = sorted(set(new_codes) - set(old_codes))
    removed = sorted(set(old_codes) - set(new_codes))
    changed = sorted(
        code
        for code in set(old_codes) & set(new_codes)
        if old_codes[code] != new_codes[code]
    )
    return {
        "first_generation": False,
        "added": added,
        "removed": removed,
        "changed": changed,
        "critical_path_changed": previous.get("critical_path")
        != current.get("critical_path"),
    }
