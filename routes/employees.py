from flask import Blueprint, request, jsonify

from models import db, Employee
from utils.utils import is_authorized

employees_bp = Blueprint('employees', __name__, url_prefix='/api/employees')

@employees_bp.route('/', methods = ['GET'])
def get_employees():
      """
      Retrieves a list of all employees associated with a specific project.
      
      Expects 'project_id' as a query parameter. Returns a JSON array containing
      dictionaries of employee data. Returns a 400 error if project_id is missing.
      """
      project_id = request.args.get('project_id')
      if not project_id:
            return jsonify({"error" : "Missing project_id"}), 400
      
      employees = Employee.query.filter_by(project_id = project_id).all()

      return jsonify([employee.to_dict() for employee in employees])
      
@employees_bp.route('/', methods = ['POST'])
def add_employee():
      data = request.get_json()

      """
      Adds a new employee to a specific project.
      
      Requires a valid authorization session token for the target project.
      Expects a JSON payload containing 'project_id', 'name', and optionally
      'role' and 'capacity' (defaults to 1.0 FTE).
      
      Returns:
          201: Success message and the new employee's ID.
          400: Error if required fields (name or project_id) are missing.
          403: Error if the user lacks edit permissions.
          500: Database error.
      """

      #Authentication check
      if not is_authorized(data['project_id']):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403
      
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
      
@employees_bp.route('/<int:emp_id>', methods = ['DELETE'])
def delete_employee(emp_id):
      """
      Deletes a specific employee from the database by their ID.
      
      Requires a valid authorization session token for the project the employee 
      belongs to.
      
      Returns:
          200: Success message upon deletion.
          403: Error if the user lacks edit permissions.
          404: Error if the employee does not exist.
          500: Database error.
      """
      emp = Employee.query.get(emp_id)
      if not emp:
            return jsonify({"error" : "Employee was not found"}), 404
      #authentication check      
      if not is_authorized(emp.project_id):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403
      
      try:
            db.session.delete(emp)
            db.session.commit()
            return jsonify({'message' : "Employee was deleted"}), 200
      except Exception as e:
            db.session.rollback()
            return jsonify({"error" : str(e)}), 500