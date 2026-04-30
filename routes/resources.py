from flask import Blueprint, request, jsonify, render_template, session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import os

from models import db, Task, Resource, Project, Employee, TaskEmployee, TaskResource
from utils.cpm import topological_sort, calculate_critical_path
from utils.utils import normalize_date, shift_dependent_tasks, calculate_delta, add_custom_days, is_authorized

resources_bp = Blueprint('resources', __name__, url_prefix='/api/resources')

@resources_bp.route('/', methods=['GET'])
def get_resources():
      """
      Retrieves a list of all resources associated with a specific project.
      
      Expects 'project_id' as a query parameter. Returns a JSON array containing
      dictionaries of resource data. Returns an empty list if project_id is missing.
      """
      project_id = request.args.get('project_id')

      if project_id:
            resources = Resource.query.filter_by(project_id = project_id).all()
            return jsonify([r.to_dict() for r in resources])
      else:
            return jsonify([])
      

@resources_bp.route('/', methods=['POST'])
def create_resource():
      """
      Creates a new resource for a specific project.
      
      Requires a valid authorization session token for the target project.
      Expects a JSON payload containing 'project_id', and optionally 'name', 
      'resource_type', 'total_amount', 'units', and 'cost_per_unit'.
      
      Returns:
          201: Success message and the new resource's ID and name.
          400: Error if project_id is missing.
          403: Error if the user lacks edit permissions.
      """
      data = request.get_json()
      
      #authentication check
      if not is_authorized(data['project_id']):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403

      if not data or 'project_id' not in data:
            return jsonify({'error' : 'Project ID missing'}), 400
      
      res = Resource(
            project_id=data['project_id'],
            name = data.get('name', ''),
            resource_type = data.get('resource_type', 'Equipment'),
            total_amount = float(data.get('total_amount', 1.0)),
            units = data.get('units', 'ks'),
            cost_per_unit = float(data.get('cost_per_unit', 0.0))
      )
      db.session.add(res)
      db.session.commit()
      return jsonify({'id': res.id, 'name': res.name, 'message' : 'Resource created'}), 201

@resources_bp.route('/', methods = ['PATCH'])
def update_resource():
      """
      Updates an existing resource's attributes.
      
      Requires a valid authorization session token for the project the resource 
      belongs to. Expects a JSON payload containing the resource 'id' and any 
      fields to be updated (e.g., 'name', 'resource_type', 'total_amount', etc.).
      
      Returns:
          204: Success (No content returned).
          400: Error if float conversion fails or ID is missing.
          403: Error if the user lacks edit permissions.
          404: Error if the resource is not found.
      """
      data = request.get_json()

      #added for authentication
      if not is_authorized(data['project_id']):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403
      
      resource = Resource.query.get_or_404(data['id'])

      # FIX: Updated column names to match the actual model (same as POST method)
      if 'name' in data: 
            resource.name = data['name']
      if 'resource_type' in data: 
            resource.resource_type = data['resource_type']
      if 'units' in data: 
            resource.units = data['units']
            
      if 'total_amount' in data:
            try:
                  resource.total_amount = float(data['total_amount'])
            except ValueError: 
                  return jsonify({"error": "Total amount must be a float number"}), 400
                  
      if 'cost_per_unit' in data:
            try:
                  resource.cost_per_unit = float(data['cost_per_unit'])
            except ValueError: 
                  return jsonify({"error": "Cost per unit must be a float number"}), 400   

      db.session.commit()
      return '', 204

@resources_bp.route('/<int:resource_id>', methods =['DELETE'])
def delete_resource(resource_id):
      """
      Deletes a specific resource from the database by its ID.
      
      Requires a valid authorization session token for the project the resource 
      belongs to.
      
      Returns:
          204: Success (No content returned) upon deletion.
          403: Error if the user lacks edit permissions.
          404: Error if the resource does not exist.
      """
      
      resource = Resource.query.get_or_404(resource_id)

      #added for authentication
      if not is_authorized(resource.project_id):
            return jsonify({'error': 'Read-only access. Invalid or missing token.'}), 403
      
      db.session.delete(resource)
      db.session.commit()
      return '', 204