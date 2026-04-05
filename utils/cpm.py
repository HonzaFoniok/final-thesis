# ----- FUNCTION for calculating CRITICAL PATH METHOD -----
# topological sort is done using Kahn's algorithm

#imports
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
    #converting all IDs to integers 
    valid_ids = {int(task['id']) for task in tasks}
    in_degree = {int(task['id']): 0 for task in tasks}  #dependencies of the task
    successors = defaultdict(list)                      #succesors of the task

    # filling the data
    for task in tasks:
        node_id = int(task['id'])
        
        # 'cleaning' if input is not int
        raw_deps = parse_dependencies(task.get('dependencies', []))
        valid_deps = [d for d in raw_deps if d in valid_ids]
        
        #number of predecessors
        in_degree[node_id] = len(valid_deps)
        for p in valid_deps:
            #waiting for predecessor
            successors[p].append(node_id)

    # put tasks without dependencies in the queque
    queue = deque([node_id for node_id in in_degree if in_degree[node_id] == 0])
    topo_order = []

    #implementing Kahn's algorithm
    while queue:
        #taking firts element from queque
        current = queue.popleft()
        topo_order.append(current)

        #going through all the tasks that were waiting for this 'current' element from queque
        for neighbor in successors[current]:
            #reducing the number of missing dependencies by one
            in_degree[neighbor] -= 1
            #adding to the queque, if there are not any dependencies left
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    #checking if the grapgh does not contain cycle
    if len(topo_order) != len(tasks):
        raise ValueError("Graph contains cycle. Critical path cannot be calculated.")

    return topo_order, successors

#function for calculating crtical path of project
def calculate_critical_path(tasks, topo_order, successors):
    cpm_data = {}
    
    for task in tasks:
        node_id = int(task['id'])
        start_str = str(task['start'])[:10]
        end_str = str(task['end'])[:10]
        
        # added include_weekends
        include_weekends = task.get('include_weekends', True)
        
        start_dt = datetime.strptime(start_str, '%Y-%m-%d')
        end_dt = datetime.strptime(end_str, '%Y-%m-%d')
        
        # calculation of actual duration (valid calendar days)
        duration = 0
        curr = start_dt
        while curr <= end_dt:
            if include_weekends or curr.weekday() < 5:
                duration += 1
            curr += timedelta(days=1)
        
        valid_ids = {int(t['id']) for t in tasks}
        raw_deps = parse_dependencies(task.get('dependencies', []))
        valid_deps = [d for d in raw_deps if d in valid_ids]
        
        cpm_data[node_id] = {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'duration': duration,
            'dependencies': valid_deps,
            'include_weekends': include_weekends
        }

    if not cpm_data:
        return [], {}
    
    # Konec celého projektu
    project_end_dt = max([data['end_dt'] for data in cpm_data.values()])

    for node_id in reversed(topo_order):
        node = cpm_data[node_id]
        include_weekends = node['include_weekends']
        
        # latest finish
        if not successors[node_id]:
            lf = project_end_dt
        else:
            lf = min([cpm_data[succ]['LS_dt'] for succ in successors[node_id]]) - timedelta(days=1)
            
        # ff the task cannot run on the weekend and the LF falls on the weekend, shorten the LF to Friday
        if not include_weekends:
            while lf.weekday() >= 5: # 5 sat, 6 san
                lf -= timedelta(days=1)
                
        node['LF_dt'] = lf
            
        # 3latest start
        ls = node['LF_dt']
        days_to_subtract = node['duration'] - 1
        
        while days_to_subtract > 0:
            ls -= timedelta(days=1)
            if not include_weekends:
                while ls.weekday() >= 5:
                    ls -= timedelta(days=1)
            days_to_subtract -= 1

        node['LS_dt'] = ls
        
        # slack
        node['slack'] = (node['LS_dt'] - node['start_dt']).days

    critical_path_ids = [node_id for node_id, data in cpm_data.items() if data['slack'] <= 0]
    
    return critical_path_ids, cpm_data

# --------------------------------------------------------
