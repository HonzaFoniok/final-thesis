from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()

#SQLAlchemy model for projects
class Project(db.Model):
    #attributes for projects
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(100), nullable = False)

    #relations
    tasks = db.relationship('Task', backref = 'project', lazy = True, cascade = "all, delete-orphan")
    resources = db.relationship('Resource', backref = 'project', lazy = True, cascade = "all, delete-orphan")

#SQLAlchemy model for Tasks
class Task(db.Model):
    #attributes for tasks
    id = db.Column(db.Integer, primary_key = True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable = False)
    name = db.Column(db.String(100))
    start = db.Column(db.String(32))
    end = db.Column(db.String(32))
    progress = db.Column(db.Integer, default=0)
    is_progress_manual = db.Column(db.Boolean, default = False)
    dependencies = db.Column(db.String(100))
    include_weekends = db.Column(db.Boolean, default = False)

    #relations
    assignments = db.relationship('TaskEmployee', backref='task', lazy=True, cascade="all, delete-orphan")
    resource_assignments = db.relationship('TaskResource', backref='task', lazy=True, cascade="all, delete-orphan" )

    def to_dict(self):
        calculated_progress = self.progress
        if not self.is_progress_manual and self.start and self.end:
            try:
                start_date = datetime.strptime(self.start, '%Y-%m-%d').date()
                end_date = datetime.strptime(self.end, '%Y-%m-%d').date()
                today = date.today()

                if today < start_date:
                    calculated_progress = 0
                elif today >= end_date:
                    calculated_progress = 100
                else:
                    days_total = (end_date - start_date).days
                    days_passed = (today - start_date).days
                    if days_total > 0:
                        calculated_progress = int((days_passed/days_total)*100)
                    else:
                        calculated_progress = 100
            except:
                pass

        return {
            "id" : self.id,
            "project_id" : self.project_id,
            "name" : self.name,
            "start" : self.start,
            "end" : self.end,
            "progress" : calculated_progress,
            "is_progress_manual": self.is_progress_manual,
            "dependencies" : self.dependencies,
            "include_weekends": bool(self.include_weekends),
            "assignments" : [assign.to_dict() for assign in self.assignments],
            "resource_assignments" : [res_assign.to_dict() for res_assign in self.resource_assignments]
        }

##SQLAlchemy model for Resources
class Resource(db.Model):
    #attributes for Resources
    id = db.Column(db.Integer, primary_key = True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable = False)
    name = db.Column(db.String(100), nullable = False)
    resource_type = db.Column(db.String(50))
    total_amount = db.Column(db.Float, default = 1.0)
    units = db.Column(db.String(20))
    cost_per_unit = db.Column(db.Float, default = 0.0)

    def to_dict(self):
        return {
            "id" : self.id,
            "project_id" : self.project_id,
            "name" : self.name,
            "resource_type" : self.resource_type,
            "total_amount" : self.total_amount,
            "units" : self.units,
            "cost_per_unit" : self.cost_per_unit
        }
    
class TaskResource(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable = False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable = False)
    quantity = db.Column(db.Float, default = 1.0)
    allocation = db.Column(db.Float, default = 1.0)

    def to_dict(self):
        return {
            "id" : self.id,
            "task_id" : self.task_id,
            "resource_id" : self.resource_id,
            "quantity" : self.quantity,
            "allocation" : self.allocation
        }

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable = False)
    name = db.Column(db.String(100), nullable = False)
    role = db.Column(db.String(100))
    capacity = db.Column(db.Float, default = 1.0)

    def to_dict(self):
        return {
            "id" : self.id,
            "project_id" : self.project_id,
            "name" : self.name,
            "role" : self.role,
            "capacity" : self.capacity
        }
    
class TaskEmployee(db.Model):
    #who works on which task
    id = db.Column(db.Integer, primary_key = True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable = False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable = False)
    allocation = db.Column(db.Float, default = 1.0)

    def to_dict(self):
        return {
            "id" : self.id,
            "task_id" : self.task_id,
            "employee_id" : self.employee_id,
            "allocation" : self.allocation
        }