from flask import Blueprint, request,render_template, session, redirect, url_for

from models import Project, Task, Employee, Resource
from utils.utils import is_authorized

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
def dashboard():
      """
      Renders the main dashboard page.
      Retrieves all projects from the database and passes them to the template.
      """
      projects= Project.query.all()
      return render_template('dashboard.html', projects = projects)

@views_bp.route('/project/<int:project_id>/tasks')
def project_tasks(project_id):
      """
      Renders the task management page (Gantt chart) for a specific project.
      
      If a valid authorization token is provided in the URL, it saves the token
      securely into the user's session and redirects to a clean URL without the token.
      """

      #if there is valid token in URL
      url_token = request.args.get('token')
      if url_token and is_authorized(project_id):
            #saving permanently to session
            if 'project_tokens' not in session:
                  session['project_tokens'] = {}
            tokens = session['project_tokens']
            tokens[str('project_id')] = url_token
            session['project_tokens'] = tokens
            session.modified = True

            #redirect to URL without ' ?token=... '
            return redirect(url_for('project_tasks', project_id=project_id))
      
      project = Project.query.get(project_id)
    
      if not project:
            return "Project was not found", 404
      return render_template('task.html', project_id=project_id, project=project)

@views_bp.route('/project/<int:project_id>/resources')
def project_resources(project_id):
      """
      Renders the resource management page for a specific project.
      """
      project = Project.query.get_or_404(project_id)
      return render_template('resources.html', project = project)

@views_bp.route('/project/<int:project_id>/employees')
def employee_page(project_id):
      """
      Renders the employee management page for a specific project.
      """
      project = Project.query.get_or_404(project_id)
      return render_template('employees.html', project=project)

@views_bp.route('/api/tasks/<int:task_id>/resource-modal', methods = ['GET'])
def get_resouce_modal(task_id):
      project_id = request.args.get('project_id')
      employees = Employee.query.filter_by(project_id = project_id).all()
      task = Task.query.get(task_id)
      assignments = {}
      if task:
            for a in task.assignments:
                  assignments[a.employee_id] = a.allocation
      
      return render_template('employee_list.html', employees = employees, assignments = assignments)

@views_bp.route('/api/tasks/<int:task_id>/material-modal', methods = ['GET'])
def get_material_modal(task_id):
      project_id = request.args.get('project_id')
      resources = Resource.query.filter_by(project_id = project_id).all()
      task = Task.query.get(task_id)
      assignments = {}
      if task:
            for a in task.resource_assignments:
                  assignments[a.resource_id] = a.quantity
      
      return render_template('resource_list.html', resources = resources, assignments = assignments)