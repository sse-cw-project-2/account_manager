####################################################################################################
# Project Name: Motive Event Management System
# Course: COMP70025 - Software Systems Engineering
# File: accountManager.py
# Description: This file defines CRUD functions for the three types of user accounts: venues,
#              artists and attendees.
#
# Authors: James Hartley, Ankur Desai, Patrick Borman, Julius Gasson, and Vadim Dunaevskiy
# Date: 2024-03-03
# Version: 2.2
#
# Notes: Updated the functions to handle a more fleshed out database schema, with additional checks
#   against injection attacks
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
    "venue": ["user_id", "venue_name", "email", "street_address", "city", "postcode"],
    "artist": ["user_id", "artist_name", "email", "genres", "spotify_artist_id"],
    "attendee": [
        "user_id",
        "first_name",
        "last_name",
        "email",
        "street_address",
        "city",
        "postcode",
    ],
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
                "message": "Email is already in use.",
            }
        else:
            # If no data is found, the email is not in use
            return {"message": "Email is not in use."}
    except Exception as e:
        # Handle any exception that might occur during the API call
        return {"error": f"An error occurred: {str(e)}"}


def is_valid_auth_id(identifier):
    """
    Checks if a string is a valid Google account ID.

    A valid Google account ID is expected to be a numeric string. This function does not
    enforce a strict length constraint due to the variability in lengths of Google account IDs
    observed historically and the potential for future changes. However, it checks for a
    reasonable length range to filter out obviously incorrect IDs.

    Args:
        identifier (str): A unique Google account ID returned by the Google authenticator API.

    Returns:
        bool: True if the identifier is a valid Google account ID, else False.
    """
    # Check if the identifier is purely numeric
    if not identifier.isdigit():
        return False

    # Adjust length range as appropriate.
    if not (10 <= len(identifier) <= 21):
        return False

    return True


def is_valid_spotify_user_id(identifier):
    """
    Checks if a string is a valid Spotify user ID.

    A valid Spotify user ID is expected to be an alphanumeric string that may include
    hyphens and underscores. This function checks the string against these criteria
    and validates its length to be within a reasonable range based on typical Spotify user IDs.

    Args:
        identifier (str): A unique Spotify user ID.

    Returns:
        bool: True if the identifier is a valid Spotify user ID, else False.
    """
    # Define the pattern for a valid Spotify user ID: alphanumeric, hyphens, and underscores
    pattern = r"^[a-zA-Z0-9-_]+$"

    # Check if the identifier matches the pattern
    if not re.match(pattern, identifier):
        return False

    # Need to tweak range as necessary -- seems reasonable for now
    if not (8 <= len(identifier) <= 32):
        return False

    return True


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
    if not is_valid_auth_id(identifier):
        return False, "Invalid or missing unique ID."

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
    total_attributes = set(attributes_schema.get(object_type, []))
    required_attributes = total_attributes - {"spotify_artist_id"}

    # Guard against non-defined attributes
    undefined_attributes = [
        key for key in validation_attributes.keys() if key not in total_attributes
    ]
    if undefined_attributes:
        message = "Additional, undefined attributes cannot be specified: "
        message += ", ".join(undefined_attributes) + ". "
        message += "Total attributes: " + str(total_attributes)
        return False, message

    # Check for attributes with empty values
    empty_value_attributes = [key for key, value in validation_attributes.items() if value == ""]

    if empty_value_attributes:
        empty_value_attributes_str = ", ".join(empty_value_attributes)
        return False, f"Cannot specify attributes with empty values: {empty_value_attributes_str}."

    return True, ""


def check_required_attributes(validation_attributes, object_type):
    """
    Checks whether the request describes the treatment of all attributes needed to create a new
        account row in the database.

    Args:
        object_type (str): One of the five types of object being stored in the database,
            ['venue', 'artist', 'attendee', 'event', 'ticket'].
        validation_attributes (dict): The attributes of that object being queried in the database.

    Returns:
        A tuple (bool, str) of True and no message if all required attribute keys are specified,
            or False and an error message if not.
    """
    # Identify attributes required for the function
    total_attributes = set(attributes_schema.get(object_type, []))
    required_attributes = total_attributes - {"spotify_artist_id"}

    # Guard against non-defined attributes
    undefined_attributes = [
        key for key in validation_attributes.keys() if key not in total_attributes
    ]
    if undefined_attributes:
        message = "Additional, undefined attributes cannot be specified: "
        message += ", ".join(undefined_attributes) + "."
        return False, message

    # Check for missing required attributes
    missing_attributes = [key for key in required_attributes if key not in validation_attributes]

    if missing_attributes:
        missing_attributes_str = ", ".join(missing_attributes)
        return False, f"Missing required attributes: {missing_attributes_str}."

    # Check for attributes with empty values
    empty_value_attributes = [key for key, value in validation_attributes.items() if value == ""]

    if empty_value_attributes:
        empty_value_attributes_str = ", ".join(empty_value_attributes)
        return False, f"Cannot specify attributes with empty values: {empty_value_attributes_str}."

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
    user_id = request["identifier"]
    attributes_to_fetch = [
        attr for attr, include in request.get("attributes", {}).items() if include
    ]

    try:
        data = (
            supabase.table(account_type + "s")
            .select(", ".join(attributes_to_fetch))
            .eq("user_id", user_id)
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
        result, error = (
            supabase.table(object_type + "s").insert(data_to_insert).execute()
        )

        # Since 'result' and 'error' are tuples, unpack them correctly
        result_key, result_value = result
        error_key, error_value = error

        # Check the content of the 'result' tuple
        if result_key == "data" and result_value:
            user_id = result_value[0].get("user_id")
            return user_id, "Account creation was successful."
        elif error_value:
            # Now checking the error_value for actual error content
            return None, f"An error occurred: {error_value}"
        else:
            return None, "Unexpected response: No data returned after insert."
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

    # Check that requirements are met
    valid, message = check_required_attributes(validation_attributes, object_type)
    if not valid:
        return False, message

    # Protection against injection attacks in the Spotify url
    spotify_artist_id = validation_attributes.get("spotify_artist_id")
    if spotify_artist_id and not is_valid_spotify_user_id(spotify_artist_id):
        message = "Invalid Spotify User ID -- field requires only the string \
        of characters following https://open.spotify.com/artist/"
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
            .eq("user_id", identifier)
        )
        result = query.execute()

        # Check if the update was successful
        if result.data:
            # Compare the updated attributes to the expected values
            updated_attributes = result.data[0]
            if all(
                updated_attributes[key] == value
                for key, value in data_to_update.items()
            ):
                return True, "Account update was successful."
            else:
                return (
                    False,
                    "Failed to update account: Attributes not updated as expected.",
                )
        else:
            return False, "Failed to update account: Record not found."

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

    valid, validation_message = validate_request(request)
    if not valid:
        return False, validation_message

    object_type = request["object_type"]
    identifier = request["identifier"]

    try:
        # Delete the record from the specified table
        result = (
            supabase.table(object_type + "s").delete().eq("user_id", identifier).execute()
        )

        # Assuming result.data contains the number of deleted rows
        if result.data:
            return True, "Account deletion was successful."
        else:
            return False, "Account not found or already deleted."
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

    if "function" not in req_data or req_data["function"] != "get":
        return jsonify({"error": "API only handles get requests"}), 400

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
    req_data = request.json

    # Check a valid payload was received
    if not req_data:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    if "function" not in req_data or req_data["function"] != "create":
        return jsonify({"error": "API only handles create requests"}), 400

    user_id, message = create_account(req_data)
    if user_id:
        return jsonify({"user_id": user_id, "message": message}), 200
    else:
        return jsonify({"error": message}), 400


@functions_framework.http
def api_update_account(request):
    req_data = request.json

    if not req_data:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    if "function" not in req_data or req_data["function"] != "update":
        return jsonify({"error": "API only handles update requests"}), 400

    success, message = update_account(req_data)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400


@functions_framework.http
def api_delete_account(request):
    req_data = request.json

    if not req_data:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    if "function" not in req_data or req_data["function"] != "delete":
        return jsonify({"error": "API only handles delete requests"}), 400

    success, message = delete_account(req_data)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400


if __name__ == "__main__":
    app.run(debug=True)
