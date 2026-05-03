from flask import Flask, session
from datetime import timedelta
import os

from models import db
from routes import register_blueprints

# ----- CONFIG and INIT ------
app = Flask(__name__, instance_relative_config=True)
app.secret_key = 'the_most_secret_key_off_all_times'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #safe memory
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

@app.before_request
def make_session_permanent():
    session.permanent = True

db.init_app(app)

with app.app_context():
      db.create_all()
# --------------------------------------------------------------------------

#register all Flask blueprints using helper function 
register_blueprints(app)

if __name__ == '__main__':
    app.run(debug=True)
