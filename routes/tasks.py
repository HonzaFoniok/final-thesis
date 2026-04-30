from flask import Blueprint, request, jsonify
from datetime import datetime

from models import db, Task, Resource, Employee, TaskEmployee, TaskResource
from utils.cpm import topological_sort, calculate_critical_path
from utils.utils import normalize_date, shift_dependent_tasks, calculate_delta, add_custom_days, is_authorized

#create a blueprint
tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

# ----- CRUD operations for tasks

#get route for all tasks
@tasks_bp.route('/', methods = ['GET'])
def get_tasks():
      """
      Retrieves all tasks for a specific project and prepares them for the Gantt view.
      
      Expects 'project_id' as a query parameter. It maps database IDs to row numbers
      for dependencies, aggregates assigned employees and resources into strings, 
      and executes the Critical Path Method (CPM) algorithm to determine which tasks 
      are critical for the project's timeline.
      
      Returns:
          200: JSON array of task dictionaries enriched with 'row_num', 
               'is_critical', 'employees_str', and 'resources_str'.
      """
      project_id = request.args.get('project_id')
      if not project_id:
            return jsonify([])
      
      
      tasks = Task.query.filter_by(project_id = project_id).order_by(Task.id).all()
      #map database ids to row numbers 
      id_to_row = {task.id: index + 1 for index, task in enumerate(tasks)} 

      result = []
      cpm_input = []
      for index, task in enumerate(tasks):
            task_dict = task.to_dict()
            row_num = index +1
            task_dict['row_num'] = row_num

            row_deps = []
            if task_dict['dependencies']:
                  
                  db_ids = [int(i.strip()) for i in task_dict['dependencies'].split(',') if i.strip()]      #get IDs from database
                  row_deps = [id_to_row[db_id] for db_id in db_ids if db_id in id_to_row]                   #translate those to row numbers
                  task_dict['dependencies'] = ", ".join(str(d) for d in row_deps)                           #send those to table
            
            #adding employees and resources to the Task table
            emp_list = []
            # lloking for all employes for current task
            assignments = TaskEmployee.query.filter_by(task_id=task.id).all()
            for assign in assignments:
                  emp = Employee.query.get(assign.employee_id)
                  if emp:
                        #emp_list.append(f"{emp.name} ({assign.quantity})")
                        emp_list.append(f"{emp.name} ({assign.allocation})")
            task_dict['employees_str'] = ", ".join(emp_list) if emp_list else ""

            resource_list = []
            for res_assign in task.resource_assignments:
                  resource = Resource.query.get(res_assign.resource_id)
                  if resource:
                        resource_list.append(f"{resource.name} ({res_assign.quantity})")
                        #resource_list.append(f"{resource.name} ({res_assign.allocation})")
            task_dict['resources_str'] = ", ".join(resource_list) if resource_list else ""

            result.append(task_dict)

            if task.start and task.end:
                  cpm_input.append({
                        'id': row_num,
                        'start': str(task.start),
                        'end': str(task.end),
                        'dependencies': row_deps,
                        'include_weekends': task.include_weekends
                  })
            
      #calculation of critical path
      critical_rows = []
      if cpm_input:
            try:
                  topo_order, successors = topological_sort(cpm_input)
                  critical_rows, _ = calculate_critical_path(cpm_input, topo_order, successors)
            except Exception as e:
                  print(f"CPM Error: {e}")

      for t in result:
            t['is_critical'] = (t['row_num'] in critical_rows)

      return jsonify(result)


@tasks_bp.route('/', methods = ['POST'])
def create_task():
      """
      Creates a new, empty task row for a specific project.
      
      Requires a valid authorization session token.
      
      Returns:
          201: Success message and the new task's ID.
          400: Error if project_id is missing.
          403: Error if the user lacks edit permissions.
      """
      data = request.get_json()
      if not data or 'project_id' not in data:
            return jsonify({'error' : 'Project ID missing'}), 400
      
      #added for authentication
      if not is_authorized(data['project_id']):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403

      task = Task(
            project_id = data['project_id'],
            name = "", start = "", end = "", progress = 0, dependencies = ""
      )
       
      db.session.add(task)
      db.session.commit()
      return jsonify({'message' : 'Task created', 'id' : task.id}), 201


@tasks_bp.route('/', methods = ['PATCH'])
def update_task_patch():
      """
      Updates specific attributes of an existing task (e.g., name, dates, dependencies).
      
      Requires a valid authorization session token. It handles date normalization, 
      recalculates duration if 'include_weekends' flag changes, and triggers the 
      'shift_dependent_tasks' function if the task's end date was modified.
      
      Returns:
          204: Success (No content returned).
          400: Validation error (e.g., invalid date format or integer).
          403: Error if the user lacks edit permissions.
          404: Error if the task is not found.
      """
      data = request.get_json()
      task = Task.query.get_or_404(data['id'])

      #added for authentication
      if not is_authorized(task.project_id):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403
      
      old_end = task.end

      if 'name' in data: task.name = data['name']
      try:
            if 'start' in data:
                  task.start = normalize_date(data['start'])
            if 'end' in data:
                  task.end = normalize_date(data['end'])
      except ValueError as e:
            return jsonify({'error': str(e)}), 400
      if 'progress' in data: 
            try: 
                  task.progress = int(data['progress'])
                  task.is_progress_manual = True
            except ValueError: 
                  return jsonify({"error":"Progress must be integer"}), 400
            except TypeError:
                  return jsonify({"error":"Progress cannot be empty."}), 400
      if 'dependencies' in data:
            tasks = Task.query.filter_by(project_id = task.project_id).order_by(Task.id).all()
            row_to_id = {index + 1: t.id for index, t in enumerate(tasks)}

            input_string = data['dependencies']
            if input_string:
                  row_nums = [int(r.strip()) for r in input_string.split(',') if r.strip().isdigit()] 
                  db_ids = [str(row_to_id[r]) for r in row_nums if r in row_to_id]
                  task.dependencies = ", ".join(db_ids)
            else:
                  task.dependencies = " "

      if 'include_weekends' in data:
            new_flag = str(data['include_weekends']).lower() in ['true', '1']
            if task.include_weekends != new_flag:
                  old_flag = task.include_weekends
                  task.include_weekends = new_flag

                  if task.start and task.end:
                        start_date = datetime.strptime(task.start, '%Y-%m-%d')
                        end_date = datetime.strptime(task.end, '%Y-%m-%d')
                        duration = calculate_delta(start_date, end_date, old_flag)
                        new_end_date = add_custom_days(start_date, duration, new_flag)
                        task.end = new_end_date.strftime('%Y-%m-%d')

      #domino effect for project delays
      delta_days = 0
      if old_end and task.end and old_end != task.end:
            shift_dependent_tasks(task.id, task.project_id)

      db.session.commit()
      return '', 204

#route for deleting task
@tasks_bp.route('/<int:task_id>', methods =['DELETE'])
def delete_task(task_id):
      """
      Deletes a specific task from the database by its ID.
      
      Requires a valid authorization session token.
      
      Returns:
          204: Success (No content returned) upon deletion.
          403: Error if the user lacks edit permissions.
          404: Error if the task does not exist.
      """
      task = Task.query.get_or_404(task_id)

      #added for authentication
      if not is_authorized(task.project_id):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403

      db.session.delete(task)
      db.session.commit()
      return '', 204

# --------------------------------------------------------------- # 


@tasks_bp.route('/<int:task_id>/assignments', methods = ['POST'])
def update_task_employee_assignments(task_id):
      """
      Updates employee assignments and their allocation for a specific task.
      
      Requires a valid authorization session token. Checks for employee capacity 
      clashes by calculating existing allocations in overlapping tasks. Replaces 
      all current assignments with the newly provided ones.
      
      Returns:
          200: Success message.
          400: Error if an employee lacks capacity due to overlapping tasks.
          403: Error if the user lacks edit permissions.
          404: Error if the task is not found.
          500: Database or processing error.
      """
      task = Task.query.get(task_id)
      if not task:
            return jsonify({"error" : "Task was not found"}), 404
      
      #added for authentication
      if not is_authorized(task.project_id):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403

      try:
            new_assignments = {}
            for key, value in request.form.items():
                  if key.startswith('emp_alloc_') and value.strip():
                        try:
                              safe_value = value.replace(',', '.')
                              alloc_val = float(safe_value)
                    
                              if alloc_val > 0:
                                    emp_id_str = key.replace('emp_alloc_', '')
                                    emp_id = int(emp_id_str)
                                    new_assignments[emp_id] = alloc_val
                        
                        except Exception as e:
                              print(f"Error in converting {key}: {str(e)}")
            
            task_start, task_end = None, None
            
            if task.start and task.end:
                  task_start = datetime.strptime(task.start, '%Y-%m-%d').date()
                  task_end = datetime.strptime(task.end, '%Y-%m-%d').date()
            
            if task_start and task_end:
                  for emp_id, req_alloc in new_assignments.items():
                        other_assignments = TaskEmployee.query.filter(
                              TaskEmployee.employee_id == emp_id,
                              TaskEmployee.task_id != task_id
                        ).all() 
            
                        overlapping_sum = 0.0
                        overlapping_tasks = []
            
                        for other_assign in other_assignments:
                              other_task = other_assign.task
                              if not other_task.start or not other_task.end: continue

                              other_start = datetime.strptime(other_task.start, '%Y-%m-%d').date()
                              other_end = datetime.strptime(other_task.end, '%Y-%m-%d').date()
            
                              if task_start <= other_end and other_start <= task_end:
                                    overlapping_sum += float(other_assign.allocation)
                                    overlapping_tasks.append(other_task.name)

                        if req_alloc + overlapping_sum > 1.0:
                              employee = Employee.query.get(emp_id)
                              tasks_str = ", ".join(overlapping_tasks)
                              avalaible = max(0.0, round(1.0 - overlapping_sum, 2))
                              return jsonify({"error" : f"Employee '{employee.name}' does not have capacity! Allready working on: {tasks_str} with {overlapping_sum}. Free capacity is {avalaible}"}), 400
            
            TaskEmployee.query.filter_by(task_id = task_id).delete()
            for emp_id, allocation in new_assignments.items():
                  new_assign = TaskEmployee(task_id = task_id, employee_id = emp_id, allocation = allocation)
                  db.session.add(new_assign)

            db.session.commit()
            return jsonify({"message" : "Employees successfully assigned!"}), 200

      except Exception as e:
            db.session.rollback()
            return jsonify({"error" : str(e)}), 500
      

@tasks_bp.route('/<int:task_id>/material-assignments', methods = ['POST'])
def update_task_material_assignments(task_id): #RENAME maybe?
      """
      Updates resource/material assignments and quantities for a specific task.
      
      Requires a valid authorization session token. Validates availability based on 
      resource type ('Material' is globally constrained, 'Equipment' is constrained 
      only across overlapping time periods).
      
      Returns:
          200: Success message.
          400: Error if resource stock or capacity is exceeded.
          403: Error if the user lacks edit permissions.
          404: Error if the task is not found.
          500: Database or processing error.
      """
      task = Task.query.get(task_id)

      #added for authentication
      if not is_authorized(task.project_id):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403
      
      if not task:
            return jsonify({"error" : "Task was not found"}), 404

      try:
            new_assignments = {}
            for key, value in request.form.items():
                  if key.startswith('mat_alloc_') and value.strip():
                        try:
                              safe_value = value.replace(',', '.')
                              quantity_value = float(safe_value)
                              if quantity_value > 0:
                                    res_id = int(key.replace('mat_alloc_', ''))
                                    new_assignments[res_id] = quantity_value
                        except ValueError:
                              print(f"Error in converting {key}: {str(e)}")
            
            #setting times for actual task
            task_start, task_end = None, None
            if task.start and task.end:
                  task_start = datetime.strptime(task.start, '%Y-%m-%d').date()
                  task_end = datetime.strptime(task.end, '%Y-%m-%d').date()

            #check of 'warehouse'
            for res_id, req_qty in new_assignments.items():
                  res = Resource.query.get(res_id) # res means resource
                  if not res: continue

                  print(f"<DEBUG>: Resource '{res.name}' have type: '{res.resource_type}'")

                  #Material - such as cables, pins etc...
                  if res.resource_type == 'Material':
                        other_usages = TaskResource.query.filter(
                              TaskResource.resource_id == res_id,
                              TaskResource.task_id != task_id
                        ).all()
                        used_elsewhere = sum(u.quantity for u in other_usages)
                        avalaible = res.total_amount - used_elsewhere

                        if req_qty > avalaible:
                              return jsonify({"error": f"Lack of material: '{res.name}'. Avalaible only {avalaible} {res.units}."}), 400

                  else: #Resources such as testbenches
                        #asking for more than we have
                        if req_qty > res.total_amount:
                              return jsonify({"error": f"Lack of equipment '{res.name}'. Avalaible only {res.total_amount} {res.units}."}), 400
                        
                        if task_start and task_end:
                              other_assignments = TaskResource.query.filter(
                                    TaskResource.resource_id == res_id,
                                    TaskResource.task_id != task_id
                              ).all()

                              overlapping_sum = 0.0
                              overlapping_tasks = []

                              for other_assign in other_assignments:
                                    other_task = other_assign.task
                                    if not other_task.start or not other_task.end: continue

                                    other_start = datetime.strptime(other_task.start, '%Y-%m-%d').date()
                                    other_end = datetime.strptime(other_task.end, '%Y-%m-%d').date()
            
                                    if task_start <= other_end and other_start <= task_end:
                                          overlapping_sum += float(other_assign.allocation)
                                          overlapping_tasks.append(other_task.name)

                              if req_qty + overlapping_sum > res.total_amount:
                                    tasks_str = ", ".join(overlapping_tasks)
                                    available = max(0.0, res.total_amount - overlapping_sum) #not used for now in the print - UPDATE THE PRINT
                                    return jsonify({"error": f"Resource '{res.name}'does not have enough capacity! Allready used in parallel task: {tasks_str} with capacity ({overlapping_sum})."}), 400
						
            TaskResource.query.filter_by(task_id = task_id).delete()
            for res_id, qty in new_assignments.items():
                  new_assign = TaskResource( task_id=task_id, resource_id = res_id, quantity = qty)
                  db.session.add(new_assign)

            db.session.commit()
            return jsonify ({"message" : "Resource was succesfully assigned"})
      
      except Exception as e:
            db.session.rollback()
            print(f"<DEBUG> Error while saving material: {str(e)}")
            return jsonify({"error" : str(e)}), 500

@tasks_bp.route('/quick-add', methods = ['POST'])
def quick_add_task():
      """
      Quickly adds a task from the Gantt schedule view modal.
      
      Requires a valid authorization session token. Locates the first empty task row 
      in the database (or creates a new one if none exist), sets its basic properties, 
      and assigns a mandatory employee and an optional resource.
      
      Returns:
          200: Success status, task ID, and message.
          400: Error if required fields (project_id, name, dates, employee_id) are missing.
          403: Error if the user lacks edit permissions.
          500: Database or assignment processing error.
      """
      data = request.get_json()

      #added for authentication
      if not is_authorized(data['project_id']):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403
      
      #normalize_date(date_str)
      project_id = data.get('project_id')
      name = data.get('name')
      start = data.get('start')
      end = data.get('end')
      employee_id = data.get('employee_id')

      if not all([project_id, name, start, end, employee_id]):
            return jsonify({"error" : "Missing required fields"}), 400

      try:
            #locating first emmpty row (without name and start)
            empty_task = Task.query.filter(
                  Task.project_id == project_id,
                  (Task.name == "") | (Task.name == None),
                  (Task.start == "") | (Task.start == None)
            ).order_by(Task.id).first()

            if empty_task:
                  empty_task.name = name
                  empty_task.start = normalize_date(start)
                  empty_task.end = normalize_date(end)
                  empty_task.include_weekends = False
                  task_to_use = empty_task
            else:
                  new_task = Task(
                        project_id = project_id,
                        name = name,
                        start = normalize_date(start),
                        end = normalize_date(end),
                        progress = 0,
                        dependencies = "",
                        include_weekends = False
                  )
                  
                  db.session.add(new_task)
                  db.session.flush() #get/block ID before final commit using flush
                  task_to_use = new_task

            new_assignment = TaskEmployee(
                  task_id=task_to_use.id,
                  employee_id=employee_id,
                  allocation=1.0
            )

            db.session.add(new_assignment)

            res_id = data.get('resource_id')
            if res_id:
                  
                  new_res_assign = TaskResource(
                        task_id=task_to_use.id,
                        resource_id=res_id
                  )
                  db.session.add(new_res_assign)
            db.session.commit()

            return jsonify({"status": "success", "task_id": task_to_use.id, "message": "Task created or updated!"})
      
      except Exception as e:
            db.session.rollback()
            print("Error during quick add:", str(e))
            return jsonify({"error": "Failed to create task and assign employee."}), 500