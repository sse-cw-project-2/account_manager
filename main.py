####################################################################################################
# Project Name: Motive Event Management System
# Course: COMP70025 - Software Systems Engineering
# File: accountManager.py
# Description: This file defines CRUD functions for the three types of user accounts: venues,
#              artists and attendees.
#
# Authors: James Hartley, Ankur Desai, Patrick Borman, Julius Gasson, and Vadim Dunaevskiy
# Date: 2024-02-19
# Version: 2.1
#
# Notes: Combined with creation, updating and deletion functions for ease of development.
#        validate_delete_request function needs to be completed for additional resilience and
#        verification. Should look into generalising functions to repeat for multiple identifiers
#        as we have done with tickets.
####################################################################################################


from flask import Flask, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import re
import functions_framework

app = Flask(__name__)

# Create a Supabase client
load_dotenv()
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# Schema for request validation
object_types = ["venue", "artist", "attendee", "event", "ticket"]
account_types = [ot for ot in object_types if ot not in ["event", "ticket"]]
non_account_types = [ot for ot in object_types if ot not in account_types]
attributes_schema = {
    "venue": ["user_id", "email", "username", "location"],
    "artist": ["user_id", "email", "username", "genre"],
    "attendee": ["user_id", "email", "username", "city"],
    "event": [
        "event_id",
        "venue_id",
        "event_name",
        "date_time",
        "total_tickets",
        "sold_tickets",
        "artist_ids",
    ],
    "ticket": ["ticket_id", "event_id", "attendee_id", "price", "redeemed", "status"],
}
# Attribute keys are paired with boolean values for get requests, or the value to be added to the
# database otherwise.
request_template = ["function", "object_type", "identifier", "attributes"]


def is_valid_email(email):
    """
    Basic email format validation to help protect against injection attacks.

    Args:
        A string containing the email address being checked.

    Returns:
        True if the string is a valid email address, else false.
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def check_email_in_use(email):
    """
    Checks if an email is registered in any of the 'venues', 'artists', or 'attendees' tables with a
        single SQL query.

    Args:
        email: A string containing the email address being checked.

    Returns:
        A dictionary with either the user_id if found, a not-in-use message if not found, or an
            error message.
    """
    # Guard against injection attacks in case third party authentication not implemented properly
    if not is_valid_email(email):
        return {"error": "Invalid email format."}

    try:
        # Executing the raw SQL query, saved on Supabase as a rpc function
        # Queries all three tables without making separate api calls
        data = supabase.rpc("check_email_in_use", {"input_email": email}).execute()

        # Check if any data was returned
        if data.data:
            # Assuming user_id is unique across all tables and found an entry
            return {
                "account_type": data.data[0]["account_type"],
                "user_id": data.data[0]["user_id"],
            }
        else:
            # If no data is found, the email is not in use
            return {"message": "Email is not in use."}
    except Exception as e:
        # Handle any exception that might occur during the API call
        return {"error": f"An error occurred: {str(e)}"}


def validate_request(request):
    """
    Function to catch as many errors in Supabase query requests as possible to avoid wasteful calls
        to the Supabase API.

    Args:
        request: A dictionary following the above request_template.

    Returns:
        A tuple (bool, str) indicating if the request template is valid and a message explaining why
            or why not.
    """
    # Common validations for all request types
    function = request.get("function")
    object_type = request.get("object_type")
    identifier = request.get("identifier")

    # Validate function
    if function not in ["get", "create", "update", "delete"]:
        return False, "Invalid function specified."

    # Validate object type
    if object_type in non_account_types:
        return False, f"Management of {object_type + 's'} is handled by a separate API."
    elif object_type not in account_types:
        return False, f"Invalid object type. Must be one of {account_types}."

    # Validate identifier based on object_type
    if not is_valid_email(identifier):
        return False, "Invalid or missing email identifier."

    # Delegate to specific validation functions based on the function type
    if function == "get":
        return validate_get_request(request)
    elif function == "create":
        return validate_create_request(request)
    elif function == "update":
        return validate_update_request(request)
    elif function == "delete":
        return validate_delete_request(request)

    return True, "Request is valid."


def extract_and_prepare_attributes(request):
    """
    Extracts and prepares validation attributes from the JSON get request for comparison against
        the requirement schema.

    Args:
        request: A dictionary following the above request_template.

    Returns:
        A tuple (str, str) containing the object type (corresponding to a database table)
            and the attributes (corresponding to the columns of the table), minus the user_id
            which is assigned automatically by the database.
    """
    # Parse request
    attributes = request.get("attributes", {})
    object_type = request.get("object_type")

    # Filter for objects that can be modified (user_id is uuid assigned by Supabase)
    validation_attributes = {k: v for k, v in attributes.items() if k != "user_id"}

    return object_type, validation_attributes


def check_for_extra_attributes(validation_attributes, object_type):
    """
    Checks for requests asking for attributes that are not in the table/should not be available to
    the user.

    Args:
        object_type (str): One of the five types of object being stored in the database,
            ['venue', 'artist', 'attendee', 'event', 'ticket'].
        validation_attributes (dict): The attributes of that object being queried in the database.

    Returns:
        A tuple (bool, str) containing True and an empty string if no additional attributes are
            present, or False and an error message otherwise.
    """
    # Identify attributes required for the function
    required_attributes = set(attributes_schema.get(object_type, [])) - {"user_id"}

    # Guard against non-defined object_type
    if not required_attributes and validation_attributes:
        return (
            True,
            "No defined schema for object type, so no attributes are considered extra.",
        )

    # Check for attributes not defined in the database
    if not all(key in required_attributes for key in validation_attributes.keys()):
        return False, "Additional, undefined attributes cannot be specified."

    return True, ""


def check_required_attributes(validation_attributes, object_type):
    """
    Checks whether the request describes the treatment of all attributes needed to carry out the
        database function.

    Args:
        object_type (str): One of the five types of object being stored in the database,
            ['venue', 'artist', 'attendee', 'event', 'ticket'].
        validation_attributes (dict): The attributes of that object being queried in the database.

    Returns:
        A tuple (bool, str) of True and no message if all required attribute keys are specified,
            or False and an error message if not.
    """
    # Identify attributes required for the function
    required_attributes = set(attributes_schema.get(object_type, [])) - {"user_id"}

    if object_type not in attributes_schema:
        return (
            False,
            f"Invalid object type '{object_type}'. Must be one of {list(attributes_schema.keys())}.",
        )

    # Check for presence of all required attribute keys, regardless of their values
    missing_attributes = required_attributes - set(validation_attributes.keys())
    if missing_attributes:
        return (
            False,
            f"Missing required attribute keys: {', '.join(missing_attributes)}.",
        )

    return True, ""


def get_account_info(request):
    """
    Fetches specified account information based on a validated request.

    Args:
        request (dict): A dictionary built according to the request template, where attribute
            values are boolean.

    Returns:
        A dictionary with requested data or an error message.
    """
    valid, message = validate_request(request)
    if not valid:
        return {"error": message}

    account_type = request.get("object_type")
    email = request["identifier"]
    attributes_to_fetch = [
        attr for attr, include in request.get("attributes", {}).items() if include
    ]

    # Construct the attributes string for the query
    attributes = ", ".join(attributes_to_fetch)

    try:
        data = (
            supabase.table(account_type + "s")
            .select(attributes)
            .eq("email", email)
            .execute()
        )
        if data.data:
            return {
                "in_use": True,
                "message": "Email is registered with user",
                "data": data.data[0],
            }
        else:
            return {"in_use": False, "message": "Email is not in use."}
    except Exception as e:
        return {"error": f"An API error occurred: {str(e)}"}


def validate_get_request(request):
    """
    Validates whether a JSON request directed to this API follows a valid template for an account
        information get request.

    Args:
        request (dict): A dictionary built according to the request template, where attribute
            values are boolean.

    Returns:
        A tuple (bool, str) of True and no message if all required attributes are specified,
            or False and an error message if not.
    """
    object_type, queried_attributes = extract_and_prepare_attributes_for_get(request)

    # Check attributes are provided for querying
    if not queried_attributes:
        return False, "Attributes must be provided for querying."

    # Validate queried attributes
    valid, message = validate_queried_attributes(queried_attributes, object_type)
    if not valid:
        return False, message

    return True, "Request is valid."


def extract_and_prepare_attributes_for_get(request):
    """
    Extracts and prepares attributes for validation from a 'get' request.

    Args:
        request (dict): A dictionary built according to the request template, where attribute
            values are boolean.

    Returns:
        A tuple (str, str) consisting of the object type and the attributes that are being queried
            in the request.
    """
    # Parse request
    attributes = request.get("attributes", [])
    object_type = request.get("object_type")

    # Convert to dictionary if 'attributes' is a list, assuming the user wants all to be true
    if isinstance(attributes, list):
        queried_attributes = {attr: True for attr in attributes}
    else:
        queried_attributes = attributes

    return object_type, queried_attributes


def validate_queried_attributes(queried_attributes, object_type):
    """
    Validates the queried attributes against the valid attributes for the object type.

    Args:
        queried_attributes (list): A list of the object attributes being queried.
        object_type (str): The type of object (Supabase table) being queried.

    Returns:
        A tuple (bool, str) of True and no message if the queried attributes match, and False and an
            error message if not.
    """
    valid_attributes = attributes_schema.get(object_type, [])
    if object_type in non_account_types:
        return False, f"Management of {object_type + 's'} is handled by a separate API."
    if object_type not in account_types:
        return (
            False,
            "Invalid object type. Must be one of ['venue', 'artist', 'attendee'].",
        )

    # Check if queried_attributes is empty
    if not queried_attributes:
        return False, "At least one valid attribute must be queried."

    for attr, value in queried_attributes.items():
        if attr not in valid_attributes:
            return False, f"Invalid attribute '{attr}' for object_type '{object_type}'."
        if not value:
            return (
                False,
                "At least one valid attribute must be queried with a true value.",
            )
    return True, ""


def create_account(request):
    """
    Creates an account in the Supabase database based on the request parameters.

    Args:
        request: A dictionary containing 'object_type', 'identifier', and 'attributes'.

    Returns:
        A tuple containing the user id and a message explaining whether the request was successful.
    """
    valid, validation_message = validate_request(request)
    if not valid:
        return None, validation_message

    object_type = request["object_type"]
    attributes = request["attributes"]

    # Construct the data to insert. Supabase automatically assigns a UUID.
    data_to_insert = {key: value for key, value in attributes.items()}

    try:
        # Insert the data into the specified table
        result = supabase.table(object_type + "s").insert(data_to_insert).execute()

        # Print the raw result to understand its structure
        print("Raw result:", result)
        print("Insert result:", result.data)

        # Example of accessing data or error (Adjust based on actual structure)
        if hasattr(result, "error") and result.error:
            return None, f"An error occurred: {result.error}"
        else:
            user_id = result.data[0].get("user_id")
            return user_id, "Account creation was successful."
    except Exception as e:
        return None, f"An exception occurred: {str(e)}"


def validate_create_request(request):
    """
    Validates a creation request for artist, venue, or attendee.

    Args:
        request (dict): The request dictionary to validate.

    Returns:
        tuple: (bool, str) indicating if the request is valid and an error message or success.
    """
    object_type, validation_attributes = extract_and_prepare_attributes(request)

    # Check all required attributes are provided
    valid, message = check_required_attributes(validation_attributes, object_type)
    if not valid:
        return False, message

    # Check for extra, undefined attributes
    valid, message = check_for_extra_attributes(validation_attributes, object_type)
    if not valid:
        return False, message

    # Check every specified attribute has a value
    if any(value == "" for value in validation_attributes.values()):
        return False, "Every specified attribute must have a value."

    return True, "Request is valid."


def update_account(request):
    """
    Updates an account in the Supabase database based on the request parameters.

    Args:
        request: A dictionary containing 'object_type', 'identifier', and 'attributes'.

    Returns:
        A tuple containing a boolean indicating success and a message.
    """
    # Assume validate_request is a function that validates the incoming request.
    # This should check that the request structure matches the expected schema
    # and that the identifier is valid for the specified object_type.
    valid, validation_message = validate_request(request)
    if not valid:
        return False, validation_message

    object_type = request["object_type"]
    identifier = request["identifier"]
    attributes = request["attributes"]

    # Filter out attributes with no value provided
    data_to_update = {
        key: value for key, value in attributes.items() if value is not None
    }

    if not data_to_update:
        return False, "No valid attributes provided for update."

    try:
        # Update the record in the specified table
        query = (
            supabase.table(object_type + "s")
            .update(data_to_update)
            .eq("identifier_column_name", identifier)
        )
        result = query.execute()

        # Check if the update was successful
        if result.error:
            return False, f"An error occurred: {result.error}"
        else:
            return True, "Account update was successful."
    except Exception as e:
        return False, f"An exception occurred: {str(e)}"


def validate_update_request(request):
    """
    Validates an update request for artist, venue, or attendee, ensuring at least one attribute
    (excluding 'user_id') is specified for update.

    Args:
        request (dict): The request dictionary to validate.

    Returns:
        tuple: (bool, str) indicating if the request is valid and an error message or success.
    """
    object_type, validation_attributes = extract_and_prepare_attributes(request)

    # There must be at least one attribute to update
    if not validation_attributes:
        return False, "At least one attribute must be specified for update."

    # Check for extra, undefined attributes
    valid, message = check_for_extra_attributes(validation_attributes, object_type)
    if not valid:
        return False, message

    return True, "Request is valid."


def delete_account(request):
    """
    Deletes an account in the Supabase database based on the request parameters.

    Args:
        request: A dictionary containing 'object_type' and 'identifier'.

    Returns:
        A tuple containing a boolean indicating success and a message.
    """
    # Assume validate_request is a function that validates the incoming request.
    # This should check that the request structure matches the expected schema
    # and that the identifier is valid for the specified object_type.
    valid, validation_message = validate_request(request)
    if not valid:
        return False, validation_message

    object_type = request["object_type"]
    identifier = request["identifier"]

    try:
        # Delete the record from the specified table
        result = (
            supabase.table(object_type + "s")
            .delete()
            .eq("identifier_column_name", identifier)
            .execute()
        )

        # Check if the delete operation was successful
        if result.error:
            return False, f"An error occurred: {result.error}"
        else:
            return True, "Account deletion was successful."
    except Exception as e:
        return False, f"An exception occurred: {str(e)}"


def validate_delete_request(request):
    """
    Validates the parameters provided for a delete request.

    Args:
        request (dict): The request dictionary to validate.

    Returns:
        tuple: (bool, str) indicating if the request is valid and an error message or success.
    """
    # Placeholder for additional verification logic
    return True, "Request is valid."


@functions_framework.http
def api_check_email_in_use(request):
    req_data = request.get_json()

    # Check that an email string has been received
    if not req_data or "email" not in req_data:
        return jsonify({"error": "Invalid or missing email in JSON payload"}), 400

    # Function call
    email = req_data["email"]
    result = check_email_in_use(email)

    # Handle the possible outcomes
    if "error" in result:
        # Return 500 status code (internal server error)
        return jsonify(result), 500
    else:
        # Return result of the email check
        return jsonify(result), 200


@functions_framework.http
def api_get_account_info(request):
    req_data = request.get_json()

    # Check a valid payload was received
    if not req_data:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    # Call function
    result = get_account_info(req_data)

    # Handle outcomes
    if "error" in result:
        # Return 404 if account not found, or 500 for all other errors in reaching the database
        return (
            jsonify(result),
            (
                404
                if result["error"] == "No account found for the provided email."
                else 500
            ),
        )

    return jsonify(result), 200


@functions_framework.http
def api_create_account(request):
    request_data = request.json
    user_id, message = create_account(request_data)
    if user_id:
        return jsonify({"user_id": user_id, "message": message}), 200
    else:
        return jsonify({"error": message}), 400


@functions_framework.http
def api_update_account(request):
    request_data = request.json
    success, message = update_account(request_data)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400


@functions_framework.http
def api_delete_account(request):
    request_data = request.json
    success, message = delete_account(request_data)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400


if __name__ == "__main__":
    app.run(debug=True)
