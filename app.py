from flask import Flask, session
from datetime import timedelta
import os
from werkzeug.middleware.proxy_fix import ProxyFix

from models import db
from routes import register_blueprints

# ----- CONFIG and INIT ------
app = Flask(__name__, instance_relative_config=True)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = 'the_most_secret_key_off_all_times'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #safe memory
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

#added for testing using ngrok
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

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
