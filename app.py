import os
import json
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, openai_request
from datetime import datetime, timedelta

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///planner.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.template_filter()
def format_date(start_time):
    if start_time is None:
        return ""

    parsed_date = datetime.fromisoformat(start_time)

    # Format the date as "MM/DD"
    formatted_date = parsed_date.strftime("%m/%d")
    return formatted_date

# Home page 
@app.route("/")
@login_required
def index():
    user_id = session["user_id"]

    # Load day from session otherwise default to current day
    date = datetime.today().strftime("%Y-%m-%d")
    if session.get("current_day") is None:
        session["current_day"] = date 
    else:
        date = session["current_day"]

    # Get scheduled tasks for current day
    scheduled_tasks = db.execute("SELECT * FROM tasks WHERE user_id = ? AND start_time LIKE ?", user_id, date + "%")

    # Convert scheduled tasks and date to json for use in script
    scheduled_tasks_json = json.dumps(scheduled_tasks)
    date_json = json.dumps({"date": date})

    # Format readable date for header
    readable_date = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")

    return render_template("index.html", scheduled_tasks=scheduled_tasks_json, current_date=date_json, readable_date=readable_date)


# Get task list for checklist page
@app.route("/tasks")
@login_required
def tasks():
    user_id = session["user_id"]

    # Get all tasks for user
    tasks = db.execute("SELECT * FROM tasks WHERE user_id = ?", user_id)
    
    return render_template("tasks.html", tasks=tasks)


# Set task completed
@app.route("/checkbox", methods=["POST"])
@login_required
def checkbox():
    # Get data from HTTP request from script
    data = request.get_json()
    task_id = data['task_id']
    status = data['status']

    # Set completed value on task
    db.execute("UPDATE tasks SET completed = ? WHERE id = ?", status, task_id)

    return redirect("/tasks")

# filter tasks
@app.route("/taskfilter")
@login_required
def taskfilter():
    # add a filter view for tasks that are completed 
    user_id = session["user_id"]
    completed_tasks = db.execute("SELECT * FROM tasks WHERE user_id = ? AND completed = 0", user_id)
    return render_template("tasks.html", tasks=completed_tasks)

# filter tasks
@app.route("/completefilter")
@login_required
def completefilter():
    # add a filter view for tasks that are completed 
    user_id = session["user_id"]
    completed_tasks = db.execute("SELECT * FROM tasks WHERE user_id = ? AND completed = 1", user_id)
    return render_template("tasks.html", tasks=completed_tasks)

# Navigate to input for next day
@app.route("/nextday", methods=["POST"])
@login_required
def nextday():
    # Get current date from session
    current_date = datetime.strptime(session["current_day"], "%Y-%m-%d")

    # Calculate next day
    next_day = current_date + timedelta(days=1)

    # Format into string and store in session
    session["current_day"] = datetime.strftime(next_day, "%Y-%m-%d")
    return redirect("/")


# Navigate to input for previous day
@app.route("/prevday", methods=["POST"])
@login_required
def prevday():
    # Get current date from session
    current_date = datetime.strptime(session["current_day"], "%Y-%m-%d")

    # Calculate previous day
    prev_day = current_date - timedelta(days=1)

    # Format into string and store in session
    session["current_day"] = datetime.strftime(prev_day, "%Y-%m-%d")

    return redirect("/")


# Week view page
@app.route("/weekview")
@login_required
def weekview():
    user_id = session["user_id"]

    # Get all scheduled tasks for user
    scheduled_tasks = db.execute("SELECT * FROM tasks WHERE user_id = ? AND start_time IS NOT NULL", user_id)

    # Convert scheduled tasks and date to json for use in script
    scheduled_tasks_string = json.dumps(scheduled_tasks)

    return render_template("weekview.html", scheduled_tasks=scheduled_tasks_string)
 

# Add task
@app.route("/add", methods=["POST"])
@login_required
def add():
    user_id = session["user_id"]

    # Get description and location
    description = request.form.get("description")
    date = request.form.get("date")
    
    start_time = datetime.strptime(date, "%m/%d")

    # Insert task into database
    db.execute("INSERT INTO tasks (user_id, description, start_time) VALUES(?, ?, ?)", user_id, description, start_time)
    return redirect("/tasks")

# Delete task
@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    db.execute("DELETE FROM tasks WHERE id = ?", id)
    return redirect("/tasks")


# Generate schedule
@app.route("/generate", methods=["POST"])
@login_required
def generate():
    user_id = session["user_id"]

    # Get paragraph input
    description = request.form.get("description")
    response = openai_request(description)

    if not description: 
        return apology("please provide a description")
    
    if not response:
        return apology("request failed")

    # Check which date we're currently at
    date_string = session["current_day"]
    date = datetime.strptime(date_string, "%Y-%m-%d")

    # Overwrite existing schedule
    db.execute("DELETE FROM tasks WHERE user_id = ? AND start_time LIKE ?", user_id, date_string + "%")
    
    # Loop through events
    schedule = response["tasks"]
    for event in schedule:
        # Parse start/end time and summary
        start_time = datetime.strptime(event["start_time"].split()[0], "%H:%M").time()
        end_time = datetime.strptime(event["end_time"].split()[0], "%H:%M").time()
        description = event["summary"]

        # Construct correct date/time
        start_datetime = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)
        
        db.execute("INSERT INTO tasks (user_id, description, start_time, end_time) VALUES(?, ?, ?, ?)", user_id, description, start_datetime, end_datetime)

    return redirect("/")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username")

        # Ensure password was submitted
        elif not password:
            return apology("must provide password")
        
        # Ensure confirmation was submitted
        elif not confirmation:
            return apology("must provide password confirmation")

        # Ensure password matches confirmation
        elif password != confirmation:
            return apology("passwords must match")

        # Check user does not already exist
        existing_user = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        if existing_user:
            return apology("username is taken")

        # Insert user
        password_hash = generate_password_hash(password)
        id = db.execute(
            "INSERT INTO users (username, hash) VALUES(?, ?)", username, password_hash
        )

        # Remember which user has logged in
        session["user_id"] = id

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
