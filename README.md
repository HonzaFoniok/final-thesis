# Final thesis

This app was created as a part of my final thesis on Department of Industrial Engineering and Managment of FME UWB in Pilsen. 

## Key Features and Funcionality

* **Dashboard:** Overview and management of all projects in one place.
* **Interactive Gantt chart:** Visualization of tasks over time.
* **Table view:** Quick editing of tasks, their duration and progress.
* **Critical Path Calculation:** Highlighting key tasks in a project.
* **Resource and employee management:** Ability to add, edit, and allocate human and material resources to individual tasks.

## Technologies used
* **Backend:** Python, Flask, Flask-SQLAlchemy
* **Database:** SQLite
* **Frontend:** HTML5, pure CSS (Flexbox), JavaScript
* **External JS libraries:** Frappe Gantt, Grid.js

## Installation and Startup Instructions

This guide assumes that you have **Python** (version 3.8 or later) installed on your computer.

### 1. Preparing the environment
First, download the project and in the terminal, move to the project folder:
```bash
cd path/to/project/final-thesis
```

### 2. Create and activate a virtual environment
It is recommended to run the application in an isolated virtual environment (venv) to avoid library conflicts
#### Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installing dependencies
Install all necessary libraries from the requirements.txt file:
```bash
pip install -r requirements.txt
```

### 4. Launch the application
Start the application with the following command:
```bash
flask run
```
Or alternatively:
```bash
python app.py
```
After successful launch, the application will run on the local server. Open your web browser and go to:
localhost:5000

Autor: Jan Foniok
Year: 2026
