import csv
import datetime
import pytz
import uuid
import json
from flask import redirect, render_template, session
from functools import wraps
from openai import OpenAI
from tqdm import tqdm

import time

openai_client = OpenAI(api_key="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")

# define apology message
def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


# OpenAI request 
def openai_request(description):
    # Construct the prompt
    prompt = f"Determine the best schedule based on the following information: {description}. Provide the schedule using 24-hour time format."

    # Define schema for response
    schema = {
        "type" : "object",
        "properties" : {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "the task description"},
                        "start_time": {"type": "string", "description": "time that task should begin in military time"},
                        "end_time": {"type": "string", "description": "time that the task should be completed in military time"}
                    }
                }
            }
        }
    }

    # Make OpenAI API call 
    completion = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful scheduling assistant"},
            {"role": "user", "content": prompt}
        ],
        functions=[{"name": "schedule", "parameters": schema}]
    )
    
    # Get response string from completion 
    response_string = completion.choices[0].message.function_call.arguments
    print(response_string)
    # Try to parse json
    try:
        response_data = json.loads(response_string)
        return response_data
    except json.JSONDecodeError as e: 
        print("Error decoding JSON: ", e)
        return None
 
 