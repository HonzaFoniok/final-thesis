from datetime import datetime, timedelta
from collections import defaultdict, deque

#function for converting input to array of integers
def parse_dependencies(deps):
    if not deps:
        return []
    if isinstance(deps, str):
        return [int(d.strip()) for d in deps.split(',') if d.strip()]
    return [int(d) for d in deps]

#topological sort of all tasks before calculating critical path
def topological_sort(tasks):
    valid_ids = {int(task['id']) for task in tasks}
    in_degree = {int(task['id']): 0 for task in tasks}
    successors = defaultdict(list)

    for task in tasks:
        node_id = int(task['id'])
        
        # 'cleaning' if input is not int
        raw_deps = parse_dependencies(task.get('dependencies', []))
        valid_deps = [d for d in raw_deps if d in valid_ids]
        
        in_degree[node_id] = len(valid_deps)
        for p in valid_deps:
            successors[p].append(node_id)

    queue = deque([node_id for node_id in in_degree if in_degree[node_id] == 0])
    topo_order = []

    while queue:
        current = queue.popleft()
        topo_order.append(current)

        for neighbor in successors[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(topo_order) != len(tasks):
        raise ValueError("Graph contains cycle. Critical path cannot be calculated.")

    return topo_order, successors


def calculate_critical_path(tasks, topo_order, successors):
    cpm_data = {}
    
    for task in tasks:
        node_id = int(task['id'])
        start_str = str(task['start'])[:10]
        end_str = str(task['end'])[:10]
        
        start_dt = datetime.strptime(start_str, '%Y-%m-%d')
        end_dt = datetime.strptime(end_str, '%Y-%m-%d')
        duration = (end_dt - start_dt).days + 1
        
        valid_ids = {int(t['id']) for t in tasks}
        raw_deps = parse_dependencies(task.get('dependencies', []))
        valid_deps = [d for d in raw_deps if d in valid_ids]
        
        cpm_data[node_id] = {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'duration': duration,
            'dependencies': valid_deps
        }

    if not cpm_data:
        return [], {}
        
    project_end_dt = max([data['end_dt'] for data in cpm_data.values()])

    for node_id in reversed(topo_order):
        node = cpm_data[node_id]
        
        if not successors[node_id]:
            node['LF_dt'] = project_end_dt
        else:
            min_succ_ls = min([cpm_data[succ]['LS_dt'] for succ in successors[node_id]])
            node['LF_dt'] = min_succ_ls - timedelta(days=1)
            
        node['LS_dt'] = node['LF_dt'] - timedelta(days=node['duration'] - 1)
        node['slack'] = (node['LS_dt'] - node['start_dt']).days

    critical_path_ids = [node_id for node_id, data in cpm_data.items() if data['slack'] <= 0]
    
    return critical_path_ids, cpm_data