# ----- HELPER FUNCTIONS ------

#imports
from datetime import datetime, timedelta
from models import Task, Project
from flask import request, session

#helper function for authentication
def is_authorized(project_id):
      project = Project.query.get(project_id)
      if not project:
            return False
      
      #trying to find token in header
      token = request.headers.get('X-Edit-Token')
      if token == "backend_session_active":
        token = None
      #token from admin URL
      if not token:
            token = request.args.get('token')
      
      #token from Flask Session
      if not token:
            saved_tokens = session.get('project_tokens', {})
            token = saved_tokens.get(str(project_id))
      
      return project.edit_token == token
                                     
# translate dates (for CPM)
def normalize_date(date_str):
      if not date_str or str(date_str) == "":
            return None
      
      date_str = str(date_str).strip()
      formats = [             # formats of inputs accepted form user
            '%Y-%m-%d',       # Frappe Gantt default YYYY-MM-DD (such as 2026-04-09)
            '%d.%m.%Y',       # Czech without spaces DD.MM.YYYY (such as 09.04.2026 or 9.4.2026)
            '%d. %m. %Y',     # Czech with spaces DD. MM. YYYY (such as 09. 04. 2026 or 9. 4. 2026)
            '%d/%m/%Y'        # Czech with slashes DD/MM/YYYY (such as 09/04/2026)
      ]

      for format in formats:
            try:
                  #try reading actual format
                  date_object = datetime.strptime(date_str, format) 
                  #return ISO format YYYY-MM-DD
                  return date_object.strftime('%Y-%m-%d')
            except ValueError:
                  continue
      
      raise ValueError(f"Unsupported format of date: {date_str}. Use DD.MM.YYYY or DD/MM/YYYY.")

# cascade shift of project if delay occurs
def shift_dependent_tasks(parent_id, project_id, visited = None):
      if visited is None:
            visited = set()

      if parent_id in visited:
            return
      
      visited.add(parent_id)
      parent_task = Task.query.get(parent_id)
      
      if not parent_task or not parent_task.end:
            return
      
      parent_end_date = datetime.strptime(parent_task.end, '%Y-%m-%d').date()
      all_tasks = Task.query.filter_by(project_id = project_id).all()   

      for task in all_tasks:
            if not task.dependencies or not task.dependencies.strip():
                  continue
            try:
                  dependency_ids = [int(x.strip()) for x in task.dependencies.split(',') if x.strip().isdigit()]
            except ValueError:
                  continue

            if parent_id in dependency_ids:
                  if task.start and task.end:
                        task_start_date = datetime.strptime(task.start, '%Y-%m-%d').date()
                        task_end_date = datetime.strptime(task.end, '%Y-%m-%d').date()
                        
                        #find latest end of all parents - there is danger of 'skipping' other dependencies
                        max_parent_end = None
                        for dependency_id in dependency_ids:
                              dep_task = next((t for t in all_tasks if t.id == dependency_id), None)
                              if dep_task and dep_task.end:
                                    dep_end = datetime.strptime(dep_task.end, '%Y-%m-%d').date() #RENAME
                                    if not max_parent_end or dep_end > max_parent_end:
                                          max_parent_end = dep_end
                        
                        if max_parent_end:
                              duration = calculate_delta(task_start_date, task_end_date, task.include_weekends)
                              new_start_date = add_custom_days(max_parent_end, 1, task.include_weekends)

                              if task_start_date != new_start_date:
                                    task.start = new_start_date.strftime('%Y-%m-%d')
                                    task.end = add_custom_days(new_start_date, duration, task.include_weekends).strftime('%Y-%m-%d')

                                    #rekurze - shift other dependencies
                                    shift_dependent_tasks(task.id, project_id, visited)

#calculates difference between working days
def calculate_delta(start_date, end_date, include_weekends = False):
      if include_weekends:
            return (end_date - start_date).days
      
      step = 1 if end_date >= start_date else -1

      current = start_date
      working_days = 0
      while current != end_date:
            current += timedelta(days = step)
            if current.weekday() < 5: #0 to 4 is Mon to Fri
                  working_days += step
      
      return working_days 

def add_custom_days(start_date, days_to_add, include_weekends = False):
      if include_weekends:
            return start_date + timedelta(days = days_to_add)
      
      current = start_date
      added = 0
      step = 1 if days_to_add > 0 else -1
      while added < abs(days_to_add):
            current += timedelta(days=step)
            if current.weekday() < 5:
                  added += 1

      return current
# ----------------------