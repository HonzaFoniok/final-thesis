from .tasks import tasks_bp
from .projects import projects_bp
from .resources import resources_bp
from .employees import employees_bp
from .views import views_bp

#helper function for registering all blueprints thus making the main function cleaner
def register_blueprints(app):
    app.register_blueprint(tasks_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(resources_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(views_bp)