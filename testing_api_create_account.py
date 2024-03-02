import requests
import json

# Endpoint URL
url = "https://us-central1-still-descent-414311.cloudfunctions.net/api_create_account"

# Construct the request payload
data = {
    "function": "create",
    "object_type": "venue",
    "identifier": "testvenue@example.com",
    "attributes": {
        "email": "testvenue@example.com",
        "username": "testvenue",
        "location": "Sample Location"
    }
}

# Convert the dictionary to a JSON-formatted string
json_data = json.dumps(data)

# Set the appropriate headers for JSON
headers = {
    'Content-Type': 'application/json',
}

# Make the POST request
response = requests.post(url, headers=headers, data=json_data)

# Check the response
if response.status_code == 200:
    print("Venue account created successfully.")
else:
    print("Failed to create account. Status code:", response.status_code)
    print("Response:", response.text)


# Construct the request payload
data = {
    "function": "create",
    "object_type": "artist",
    "identifier": "testartist@example.com",
    "attributes": {
        "email": "testartist@example.com",
        "username": "testartist",
        "genre": "Smooth jazzzzz"
    }
}

# Convert the dictionary to a JSON-formatted string
json_data = json.dumps(data)

# Set the appropriate headers for JSON
headers = {
    'Content-Type': 'application/json',
}

# Make the POST request
response = requests.post(url, headers=headers, data=json_data)

# Check the response
if response.status_code == 200:
    print("Venue account created successfully.")
else:
    print("Failed to create account. Status code:", response.status_code)
    print("Response:", response.text)



# Construct the request payload
data = {
    "function": "create",
    "object_type": "attendee",
    "identifier": "testattendee@example.com",
    "attributes": {
        "email": "testattendee@example.com",
        "username": "testattendee",
        "city": "Flavourtown, USA"
    }
}

# Convert the dictionary to a JSON-formatted string
json_data = json.dumps(data)

# Set the appropriate headers for JSON
headers = {
    'Content-Type': 'application/json',
}

# Make the POST request
response = requests.post(url, headers=headers, data=json_data)

# Check the response
if response.status_code == 200:
    print("Venue account created successfully.")
else:
    print("Failed to create account. Status code:", response.status_code)
    print("Response:", response.text)