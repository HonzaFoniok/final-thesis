from flask import Blueprint, request, jsonify, session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta


from models import db, Task, Resource, Project, Employee, TaskEmployee
from utils.utils import is_authorized

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')

# ----- CRUD operations for projects -----

#creating a project
@projects_bp.route('/', methods = ['POST'])
def create_project():
      """
      Creates a new project and initializes it with empty task rows.
      
      Expects a JSON payload with an optional 'name' field. Upon creation,
      it generates 10 empty tasks for the Gantt chart and automatically 
      grants the creator admin rights by saving the project's edit token 
      into their secure session.
      
      Returns:
          201: Success message and the generated project ID.
          400: Error if a project with the same name already exists.
          500: Database error.
      """

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

            #saving token to session
            if 'project_tokens' not in session:
                session['project_tokens'] = {}

            #reassignment for Flask to recognize change in dict
            tokens = session['project_tokens']
            tokens[str(new_project.id)] = new_project.edit_token
            session['project_tokens'] = tokens
            session.modified = True
                  
            return jsonify({'message' : 'Project created', 'id' : new_project.id,}), 201
      
      #unique name of project
      except IntegrityError:
            db.session.rollback()
            return jsonify({'error':f"Project with name '{name}' allready exists!"}), 400
      
      except Exception as e:
            db.session.rollback()
            return jsonify({'error' : str(e)}), 500 
      
@projects_bp.route('/<int:project_id>', methods = ['DELETE'])
def delete_project(project_id):
      """
      Deletes a project and all its associated data.
      
      Requires a valid authorization session token for the project. The deletion
      of related entities (Tasks, Employees, Resources) is expected to be handled 
      by SQLAlchemy cascade rules.
      
      Returns:
          204: Success (No content returned) upon deletion.
          403: Error if the user lacks edit permissions.
          404: Error if the project is not found.
          500: Database error.
      """
      #added authorization check
      if not is_authorized(project_id):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403
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
      
@projects_bp.route('/<int:project_id>/schedule', methods = ['GET'])
def get_project_schedule(project_id):
      """
      Retrieves the project schedule for the Gantt chart timeline view.
      
      Fetches all employees and their assigned tasks within the specified 
      project. Calculates the overall timeline (min and max dates) based 
      on existing task dates, or defaults to a 14-day window from today 
      if no tasks exist.
      
      Returns:
          200: JSON object containing 'status', 'min_date', 'max_date', 
               and an array of employee 'schedule' data.
      """
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
                        resource_list = []
                        for res_assign in t.resource_assignments:

                              res = Resource.query.get(res_assign.resource_id)
                              if res:
                                    resource_list.append(res.name)
                        
                        res_str = ", ".join(resource_list) if resource_list else "No resource assigned"
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