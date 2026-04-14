from flask import Flask, request, jsonify, render_template
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import os

from models import db, Task, Resource, Project, Employee, TaskEmployee, TaskResource
from utils.cpm import topological_sort, calculate_critical_path
from utils.utils import normalize_date, shift_dependent_tasks, calculate_delta, add_custom_days

# ----- INIT ------
app = Flask(__name__, instance_relative_config=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #safe memory
db.init_app(app)

with app.app_context():
      db.create_all()
# --------------------------------------------------------------------------

# ----- API for DASHBOARD ----- 
@app.route('/')
def dashboard():
      projects= Project.query.all()
      return render_template('dashboard.html', projects = projects)

#tasks of each project
@app.route('/project/<int:project_id>/tasks')
def project_tasks(project_id):       
      project = Project.query.get_or_404(project_id)
      return render_template('task.html', project = project)

#resources of each project
@app.route('/project/<int:project_id>/resources')
def project_resources(project_id):
      project = Project.query.get_or_404(project_id)
      return render_template('resources.html', project = project)

#move the employee route here
@app.route('/project/<int:project_id>/employees')
def employee_page(project_id):
      project = Project.query.get_or_404(project_id)
      return render_template('employees.html', project=project)

# ----- API FOR PROJECTS -----

#creating a project
@app.route('/api/projects', methods = ['POST'])
def create_project():
      data = request.get_json()
      name = data.get('name', 'New project')
      try:
            #creating the project
            new_project = Project(name = name)
            db.session.add(new_project)
            db.session.commit()

            #creating 10 empty rows of tasks - for table in Gantt view
            for _ in range(10):
                  task = Task(project_id = new_project.id, name = "", start = "", end = "", progress = 0, dependencies = 0)
                  db.session.add(task)

            db.session.commit()
            return jsonify({'message' : 'Project created', 
                            'id' : new_project.id,
                            'edit_token': new_project.edit_token
                            }), 201
      
      #unique name of project
      except IntegrityError:
            db.session.rollback()
            return jsonify({'error':f"Project with name {name} allready exists!"}), 400
      
      except Exception as e:
            db.session.rollback()
            return jsonify({'error' : str(e)}), 500
      
#deleting a project
@app.route('/api/projects/<int:project_id>', methods = ['DELETE'])
def delete_project(project_id):
      #making sure all details are deleted
      try:
            """"Employee.query.filter_by(project_id=project_id).delete()
            Task.query.filter_by(project_id=project_id).delete()
            Resource.query.filter_by(project_id=project_id).delete()
            """
            project = Project.query.get_or_404(project_id)
            db.session.delete(project)
            db.session.commit()
            return jsonify({"message": "Project and all data deleted."}), 204
      except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Error while deleting project."}), 500
# -----------------------------

# ----- API FOR TASKS ----- 

#get all tasks
@app.route('/api/tasks/', methods = ['GET'])
def get_tasks():
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

@app.route('/api/tasks/<int:task_id>/resource-modal', methods = ['GET'])
def get_resouce_modal(task_id):
      project_id = request.args.get('project_id')
      employees = Employee.query.filter_by(project_id = project_id).all()
      task = Task.query.get(task_id)
      assignments = {}
      if task:
            for a in task.assignments:
                  assignments[a.employee_id] = a.allocation
      
      return render_template('employee_list.html', employees = employees, assignments = assignments)

@app.route('/api/tasks/<int:task_id>/assignments', methods = ['POST']) #EMPLOYEES, tohle presunout
def update_task_assignments(task_id):
      task = Task.query.get(task_id)
      if not task:
            return jsonify({"error" : "Task was not found"}), 404
      
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

#POST - create new task
@app.route('/api/tasks/', methods = ['POST'])
def create_task():
      data = request.get_json()
      if not data or 'project_id' not in data:
            return jsonify({'error' : 'Project ID missing'}), 400
       
      task = Task(
            project_id = data['project_id'],
            name = "", start = "", end = "", progress = 0, dependencies = ""
      )
       
      db.session.add(task)
      db.session.commit()
      return jsonify({'message' : 'Task created', 'id' : task.id}), 201

#PATCH - modify an item
@app.route('/api/tasks/', methods = ['PATCH'])
def update_task_patch():
      data = request.get_json()
      task = Task.query.get_or_404(data['id'])
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

#route for accepting data from modal in schdeule view
@app.route('/api/tasks/quick-add', methods = ['POST'])
def quick_add_task():
      data = request.get_json()
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
            db.session.commit()

            return jsonify({"status": "success", "task_id": task_to_use.id, "message": "Task created or updated!"})
      
      except Exception as e:
            db.session.rollback()
            print("Error during quick add:", str(e))
            return jsonify({"error": "Failed to create task and assign employee."}), 500


#route for deleting task
@app.route('/api/tasks/<int:task_id>', methods =['DELETE'])
def delete_task(task_id):
      task = Task.query.get_or_404(task_id)
      db.session.delete(task)
      db.session.commit()
      return '', 204

# -------------------------

# ----- API FOR RESOURCES ----- 
@app.route('/api/resources/', methods=['GET'])
def get_resources():
      project_id = request.args.get('project_id')

      if project_id:
            resources = Resource.query.filter_by(project_id = project_id).all()
            return jsonify([r.to_dict() for r in resources])
      else:
            return jsonify([])
      
@app.route('/api/resources/', methods=['POST'])
def create_resource():
      data = request.get_json()
      if not data or 'project_id' not in data:
            return jsonify({'error' : 'Project ID missing'}), 400
      
      res = Resource(project_id=data['project_id'],
                     name = data.get('name', ''),
                     resource_type = data.get('resource_type', 'Equipment'),
                     total_amount = float(data.get('total_amount', 1.0)),
                     units = data.get('units', 'ks'),
                     cost_per_unit = float(data.get('cost_per_unit', 0.0))
      )
      db.session.add(res)
      db.session.commit()
      return jsonify({'id': res.id, 'name': res.name, 'message' : 'Resource created'}), 201

@app.route('/api/resources/', methods = ['PATCH'])
def update_resource():
      data = request.get_json()
      resource = Resource.query.get_or_404(data['id'])

      if 'name' in data: resource.name = data['name']
      if 'type' in data: resource.type = data['type']
      if 'material' in data: resource.material = data['material']
      if 'rate' in data:
            try:
                  resource.rate = float(data['rate'])
            except ValueError: 
                  return jsonify({"error":"Rate mus be float"}), 400
            
      if 'units' in data: resource.units = data['units']    

      db.session.commit()
      return '', 204

@app.route('/api/resources/<int:resource_id>', methods =['DELETE'])
def delete_resource(resource_id):
      resource = Resource.query.get_or_404(resource_id)
      db.session.delete(resource)
      db.session.commit()
      return '', 204


# -----------------------------

# ----- POP-UP for RESOURCES -----

@app.route('/api/tasks/<int:task_id>/material-modal', methods = ['GET'])
def get_material_modal(task_id):
      project_id = request.args.get('project_id')
      resources = Resource.query.filter_by(project_id = project_id).all()
      task = Task.query.get(task_id)
      assignments = {}
      if task:
            for a in task.resource_assignments:
                  assignments[a.resource_id] = a.quantity
      
      return render_template('resource_list.html', resources = resources, assignments = assignments)

@app.route('/api/tasks/<int:task_id>/material-assignments', methods = ['POST'])
def update_task_material_assignments(task_id): #RENAME maybe? 
      task = Task.query.get(task_id)
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

# --------------------------------

# ----- API FOR EMPLOYEES -----

@app.route('/api/employees/', methods = ['GET'])
def get_employees():
      project_id = request.args.get('project_id')
      if not project_id:
            return jsonify({"error" : "Missing project_id"}), 400
      
      employees = Employee.query.filter_by(project_id = project_id).all()

      return jsonify([employee.to_dict() for employee in employees])
      
@app.route('/api/employees', methods = ['POST'])
def add_employee():
      data = request.get_json()
      project_id = data.get('project_id')
      name = data.get('name')
      role = data.get('role', '')
      capacity = data.get('capacity', 1.0) #default value is 1 FTE

      if not name or not project_id:
            return jsonify({"error" : "Missing name or ID of project."}), 400

      try:
            new_emp = Employee(
                  project_id = project_id,
                  name = name,
                  role = role,
                  capacity = float(capacity)
            )
            db.session.add(new_emp)
            db.session.commit()
            return jsonify({"message" : "Employee was sucsessfully added", "id" : new_emp.id}), 201
      except Exception as e:
            db.session.rollback()
            return jsonify({"error" : str(e)}), 500
      
@app.route('/api/employees/<int:emp_id>', methods = ['DELETE'])
def delete_employee(emp_id):
      emp = Employee.query.get(emp_id)
      if not emp:
            return jsonify({"error" : "Employee was not found"}), 404
      
      try:
            db.session.delete(emp)
            db.session.commit()
            return jsonify({'message' : "Employee was deleted"}), 200
      except Exception as e:
            db.session.rollback()
            return jsonify({"error" : str(e)}), 500
      

#route for the great grand table aka schedule
@app.route('/api/projects/<int:project_id>/schedule', methods = ['GET'])
def get_project_schedule(project_id):
      employees = Employee.query.filter_by(project_id = project_id).all()
      
      tasks = Task.query.filter(Task.project_id == project_id, Task.start != "", Task.end != "").all()

      if tasks:
            start_dates = [datetime.strptime(task.start, '%Y-%m-%d').date() for task in tasks]
            end_dates = [datetime.strptime(task.end, '%Y-%m-%d').date() for task in tasks]
            min_date = min(start_dates)
            max_date = max(end_dates)
      else:
            min_date = datetime.now().date()
            max_date = min_date + timedelta(days=13) # or week?
      schedule_data = []

      #find for each employee his tasks
      for employee in employees:
            emp_tasks = []
            assignments = TaskEmployee.query.filter_by(employee_id = employee.id).all()
            for assign in assignments:
                  t =  assign.task
                  if t.start and t.end:
                        # loading data for tooltip
                        res_list = [f"{r.resource.name}" for r in t.resource_assignments if r.resource]
                        res_str = ", ".join(res_list) if res_list else "No resource assigned"

                        emp_tasks.append({
                              "task_id": t.id,
                              "task_name": t.name,
                              "start": t.start,
                              "end": t.end,
                              "allocation": assign.allocation,
                              "include_weekends": t.include_weekends,
                              "resources": res_str   
                        })
                  
            schedule_data.append({
                  "emp_id": employee.id,
                  "emp_name": employee.name,
                  "tasks": emp_tasks
            })

      return jsonify({
            "status": "ok",
            "min_date": min_date.strftime('%Y-%m-%d'),
            "max_date": max_date.strftime('%Y-%m-%d'),
            "schedule": schedule_data
      })

#------------------------

if __name__ == '__main__':
    app.run(debug=True)