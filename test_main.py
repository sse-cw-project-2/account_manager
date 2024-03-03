####################################################################################################
# Project Name: Motive Event Management System
# Course: COMP70025 - Software Systems Engineering
# File: testAccountManager.py
# Description: This file contains unit tests for each function in the accountManager.py file.
#
# Authors: James Hartley, Ankur Desai, Patrick Borman, Julius Gasson, and Vadim Dunaevskiy
# Date: 2024-02-19
# Version: 2.1
#
# Notes: Supabase interactions tested using patch and MagicMock from unittest.mock. Unit tests for
#        validate_delete_request are still outstanding.
####################################################################################################


import unittest
from unittest.mock import patch, MagicMock
from main import (
    is_valid_email,
    check_email_in_use,
    is_valid_spotify_user_id,
    is_valid_auth_id,
    validate_request,
    extract_and_prepare_attributes,
    check_for_extra_attributes,
    check_required_attributes,
    get_account_info,
    validate_get_request,
    extract_and_prepare_attributes_for_get,
    validate_queried_attributes,
    create_account,
    validate_create_request,
    update_account,
    validate_update_request,
    delete_account,
)


class TestEmailValidation(unittest.TestCase):
    def test_valid_email(self):
        self.assertTrue(is_valid_email("test@example.com"))

    def test_missing_domain(self):
        self.assertFalse(is_valid_email("test@"))

    def test_missing_at_symbol(self):
        self.assertFalse(is_valid_email("testexample.com"))

    def test_invalid_characters(self):
        self.assertFalse(is_valid_email("test@exa$mple.com"))

    def test_invalid_domain(self):
        self.assertFalse(is_valid_email("test@example"))

    def test_empty_string(self):
        self.assertFalse(is_valid_email(""))


class TestCheckEmailInUse(unittest.TestCase):

    @patch("main.supabase")
    def test_email_in_use(self, mock_supabase):
        # Mock the response from Supabase
        mock_supabase.rpc.return_value.execute.return_value.data = [
            {
                "account_type": "venue",
                "message": "Email is already in use.",
                "user_id": "123",
            }
        ]

        result = check_email_in_use("test@example.com")
        self.assertEqual(
            result,
            {
                "account_type": "venue",
                "message": "Email is already in use.",
                "user_id": "123",
            },
        )

    @patch("main.supabase")
    def test_email_not_in_use(self, mock_supabase):
        # Mock the response to indicate no data found
        mock_supabase.rpc.return_value.execute.return_value.data = []

        result = check_email_in_use("new@example.com")
        self.assertEqual(result, {"message": "Email is not in use."})

    @patch("main.supabase")
    def test_invalid_email_format(self, mock_supabase):
        # Test for invalid email format, which should not even attempt to query Supabase
        result = check_email_in_use("invalid-email")
        self.assertEqual(result, {"error": "Invalid email format."})

    @patch("main.supabase")
    def test_supabase_error(self, mock_supabase):
        # Mock an exception being raised during the Supabase call
        mock_supabase.rpc.side_effect = Exception("Supabase query failed")

        result = check_email_in_use("error@example.com")
        self.assertEqual(result, {"error": "An error occurred: Supabase query failed"})


class TestSpotifyIdValidation(unittest.TestCase):
    def test_valid_url(self):
        self.assertTrue(is_valid_spotify_user_id("4a0SGxC38bo29VPaHtiFBf"))

    def test_invalid_chars_in_url(self):
        self.assertFalse(is_valid_spotify_user_id("4a0SGx@C38//bo29VPaHtiFBf"))

    def test_too_short_url(self):
        self.assertFalse(is_valid_spotify_user_id("4a0SG"))

    def test_too_long_url(self):
        self.assertFalse(is_valid_spotify_user_id("4a0SGxCPaf438bo29Va38bHtiFBo2Hti0SGxCFBf9VPa"))


class TestGoogleIdValidation(unittest.TestCase):
    def test_valid_id(self):
        self.assertTrue(is_valid_auth_id("1465835860573088967"))

    def test_invalid_chars_in_id(self):
        self.assertFalse(is_valid_auth_id("146583586@05733597/088967"))

    def test_too_short_url(self):
        self.assertFalse(is_valid_auth_id("1234"))

    def test_too_long_url(self):
        self.assertFalse(is_valid_auth_id("14658358605733597088967146583586057335970889671465835860573359708896714658358605733597088967"))


class TestValidateRequest(unittest.TestCase):

    def test_email_validation(self):
        self.assertTrue(is_valid_email("test@example.com"))
        self.assertFalse(is_valid_email("invalid-email"))

    def test_valid_requests_with_attributes(self):
        request = {
            "function": "get",
            "object_type": "venue",
            "identifier": "123456789101112",
            "attributes": {"user_id": True, "city": True, "postcode": True},
        }
        self.assertEqual(validate_request(request), (True, "Request is valid."))

    def test_request_with_nonexistant_attributes(self):
        request = {
            "function": "get",
            "object_type": "artist",
            "identifier": "1234567891011",
            "attributes": {"user_id": True, "genres": True, "extra_field": False},
        }
        valid, message = validate_request(request)
        self.assertFalse(valid)
        self.assertIn("extra_field", message)

    def test_invalid_id_in_request(self):
        request = {
            "function": "get",
            "object_type": "artist",
            "identifier": "invalid-email",
            "attributes": {"user_id": True, "genre": True},
        }
        self.assertEqual(
            validate_request(request), (False, "Invalid or missing unique ID.")
        )

    def test_missing_id(self):
        request = {
            "function": "get",
            "object_type": "artist",
            "identifier": "",
            "attributes": {
                "user_id": True,
                "email": True,
                "username": False,
                "genre": False,
            },
        }
        self.assertEqual(
            validate_request(request), (False, "Invalid or missing unique ID.")
        )

    def test_event_object_type(self):
        request = {
            "function": "get",
            "object_type": "event",
            "identifier": "example@example.com",
            "attributes": {
                "user_id": True,
            },
        }
        self.assertEqual(
            validate_request(request),
            (False, "Management of events is handled by a separate API."),
        )

    def test_ticket_object_type(self):
        request = {
            "function": "get",
            "object_type": "ticket",
            "identifier": "example@example.com",
            "attributes": {
                "user_id": True,
            },
        }
        self.assertEqual(
            validate_request(request),
            (False, "Management of tickets is handled by a separate API."),
        )

    def test_invalid_account_type(self):
        request = {
            "function": "get",
            "object_type": "non-defined_account_type",
            "identifier": "example@example.com",
            "attributes": {"user_id": True, "genre": True},
        }
        self.assertEqual(
            validate_request(request),
            (
                False,
                "Invalid object type. Must be one of "
                "['venue', 'artist', 'attendee'].",
            ),
        )

    def test_missing_account_type(self):
        request = {
            "function": "get",
            "identifier": "example@example.com",
            "attributes": {"user_id": True, "genre": True},
        }
        self.assertEqual(
            validate_request(request),
            (
                False,
                "Invalid object type. Must be one of "
                "['venue', 'artist', 'attendee'].",
            ),
        )

    def test_request_with_all_false_attributes(self):
        request = {
            "function": "get",
            "object_type": "artist",
            "identifier": "123456789101112",
            "attributes": {
                "user_id": False,
                "email": False,
                "genre": False,
            },
        }
        self.assertEqual(
            validate_request(request),
            (False, "At least one valid attribute must be queried with a true value."),
        )


class TestExtractAndPrepareAttributes(unittest.TestCase):
    def test_with_full_request(self):
        request = {
            "object_type": "artist",
            "attributes": {"name": "John Doe", "genre": "Rock", "user_id": "12345"},
        }
        expected = ("artist", {"name": "John Doe", "genre": "Rock"})
        self.assertEqual(extract_and_prepare_attributes(request), expected)

    def test_with_user_id_present(self):
        request = {
            "object_type": "venue",
            "attributes": {"location": "Downtown", "user_id": "67890"},
        }
        expected = ("venue", {"location": "Downtown"})
        self.assertEqual(extract_and_prepare_attributes(request), expected)

    def test_with_empty_attributes(self):
        request = {"object_type": "attendee", "attributes": {}}
        expected = ("attendee", {})
        self.assertEqual(extract_and_prepare_attributes(request), expected)

    def test_with_no_attributes_key(self):
        request = {"object_type": "event"}
        expected = ("event", {})
        self.assertEqual(extract_and_prepare_attributes(request), expected)

    def test_with_missing_object_type(self):
        request = {"attributes": {"title": "Concert", "date": "2024-01-01"}}
        expected = (None, {"title": "Concert", "date": "2024-01-01"})
        self.assertEqual(extract_and_prepare_attributes(request), expected)

    def test_with_additional_keys(self):
        request = {
            "object_type": "ticket",
            "attributes": {"seat": "A1", "user_id": "54321"},
            "extra_key": "extra_value",
        }
        expected = ("ticket", {"seat": "A1"})
        self.assertEqual(extract_and_prepare_attributes(request), expected)


class TestCheckForExtraAttributes(unittest.TestCase):

    # Mock attributes_schema for testing
    attributes_schema = {
        "venue": ["user_id", "venue_name", "email", "street_address", "city", "postcode"],
        "artist": ["user_id", "artist_name", "email", "genres", "spotify_artist_id"],
        "attendee": ["user_id", "first_name", "last_name", "email", "street_address", "city", "postcode"],
        "event": ["event_id", "venue_id", "event_name", "date_time", "total_tickets", "sold_tickets", "artist_ids"],
        "ticket": ["ticket_id", "event_id", "attendee_id", "price", "redeemed", "status"],
    }

    @patch("main.attributes_schema", attributes_schema)
    def test_with_extra_attributes(self):
        validation_attributes = {
            "name": "John Doe",
            "genre": "Rock",
            "extra": "Not Allowed",
        }
        object_type = "artist"
        self.assertFalse(
            check_for_extra_attributes(validation_attributes, object_type)[0]
        )

    @patch("main.attributes_schema", attributes_schema)
    def test_with_all_required_attributes(self):
        validation_attributes = {
            "user_id": "1234456789101112",
            "venue_name": "The Julius Bar",
            "email": "testvenue@example.com",
            "street_address": "1 Road Street",
            "postcode": "AB1 2CD",
            "city": "London"
        }

        object_type = "venue"
        success, message = check_for_extra_attributes(validation_attributes, object_type)

        # self.assertTrue(success)
        self.assertEqual(message, "")

    @patch("main.attributes_schema", attributes_schema)
    def test_object_type_not_in_schema(self):
        validation_attributes = {"field": "value"}
        object_type = "nonexistent"
        self.assertFalse(
            check_for_extra_attributes(validation_attributes, object_type)[0],
            "Should return False as there are no defined attributes in the schema.",
        )

    @patch("main.attributes_schema", attributes_schema)
    def test_empty_validation_attributes(self):
        validation_attributes = {}
        object_type = "artist"
        self.assertTrue(
            check_for_extra_attributes(validation_attributes, object_type)[0],
            "Should return True as empty attributes cannot include extra ones.",
        )


class TestCheckRequiredAttributes(unittest.TestCase):
    # Mock attributes_schema for testing
    attributes_schema = {
        "artist": {"name", "genre", "country"},
        "venue": {"location", "capacity"},
    }

    @patch("main.attributes_schema", attributes_schema)
    def test_all_required_attributes_provided(self):
        validation_attributes = {"name": "John Doe", "genre": "Rock", "country": "USA"}
        object_type = "artist"
        self.assertTrue(
            check_required_attributes(validation_attributes, object_type)[0]
        )

    @patch("main.attributes_schema", attributes_schema)
    def test_missing_required_attributes(self):
        validation_attributes = {
            "name": "John Doe",
            "genre": "Rock",
        }  # Missing 'country'
        object_type = "artist"
        self.assertFalse(
            check_required_attributes(validation_attributes, object_type)[0]
        )

    @patch("main.attributes_schema", attributes_schema)
    def test_object_type_not_in_schema(self):
        validation_attributes = {"field": "value"}
        object_type = "nonexistent"
        self.assertFalse(
            check_required_attributes(validation_attributes, object_type)[0],
            "Should return False as there are no defined required attributes to request.",
        )

    @patch("main.attributes_schema", attributes_schema)
    def test_empty_validation_attributes(self):
        validation_attributes = {}
        object_type = "artist"
        # Since 'artist' has required attributes and none are provided, expecting False
        self.assertFalse(
            check_required_attributes(validation_attributes, object_type)[0],
            "Should return False as required attributes are missing.",
        )


class TestGetAccountInfo(unittest.TestCase):

    @patch("main.supabase")
    @patch("main.validate_request")
    def test_valid_request_with_account_found(self, mock_validate, mock_supabase):
        # Mock validate_request to return valid
        mock_validate.return_value = (True, "Request is valid.")
        # Mock Supabase response
        mock_supabase.table().select().eq().execute.return_value.data = [
            {"user_id": "123"}
        ]

        request = {
            "function": "get",
            "object_type": "venue",
            "identifier": "new@example.com",
            "attributes": {"user_id": True, "username": True},
        }
        result = get_account_info(request)
        self.assertTrue(result["in_use"])
        self.assertIn("Email is registered with user", result["message"])

    @patch("main.supabase")
    @patch("main.validate_request")
    def test_valid_request_no_account_found(self, mock_validate, mock_supabase):
        mock_validate.return_value = (True, "Request is valid.")
        mock_supabase.table().select().eq().execute.return_value.data = []

        request = {
            "function": "get",
            "object_type": "venue",
            "identifier": "new@example.com",
            "attributes": {"user_id": True, "username": True},
        }
        result = get_account_info(request)
        self.assertFalse(result["in_use"])
        self.assertEqual(result["message"], "Email is not in use.")

    @patch("main.validate_request")
    def test_invalid_function(self, mock_validate):
        mock_validate.return_value = (False, "Invalid function specified.")

        request = {
            "function": "undefined",
            "object_type": "unknown",
            "identifier": "new@example.com",
        }
        result = get_account_info(request)
        self.assertEqual(result, {"error": "Invalid function specified."})

    @patch("main.supabase")
    @patch("main.validate_request")
    def test_api_error(self, mock_validate, mock_supabase):
        mock_validate.return_value = (True, "Request is valid.")
        mock_supabase.table().select().eq().execute.side_effect = Exception("API error")

        request = {
            "function": "get",
            "object_type": "venue",
            "identifier": "new@example.com",
            "attributes": {"user_id": True, "username": True},
        }
        result = get_account_info(request)
        self.assertTrue("error" in result)
        self.assertEqual(result["error"], "An API error occurred: API error")


class TestValidateGetRequest(unittest.TestCase):
    @patch("main.extract_and_prepare_attributes_for_get")
    @patch("main.validate_queried_attributes")
    def test_successful_validation(self, mock_validate_queried, mock_extract):
        # Setup mock responses
        mock_extract.return_value = ("artist", {"name": True, "genre": True})
        mock_validate_queried.return_value = (True, "")

        request = {"object_type": "artist", "attributes": ["name", "genre"]}
        valid, message = validate_get_request(request)

        self.assertTrue(valid)
        self.assertEqual(message, "Request is valid.")

    @patch("main.extract_and_prepare_attributes_for_get")
    def test_no_attributes_provided(self, mock_extract):
        # Setup mock response to simulate no attributes provided
        mock_extract.return_value = ("artist", {})

        request = {"object_type": "artist"}
        valid, message = validate_get_request(request)

        self.assertFalse(valid)
        self.assertEqual(message, "Attributes must be provided for querying.")

    @patch("main.extract_and_prepare_attributes_for_get")
    @patch("main.validate_queried_attributes")
    def test_queried_attributes_validation_fails(
        self, mock_validate_queried, mock_extract
    ):
        # Setup mock responses to simulate queried attributes validation failure
        mock_extract.return_value = ("artist", {"name": True})
        mock_validate_queried.return_value = (False, "Invalid attribute")

        request = {"object_type": "artist", "attributes": ["name"]}
        valid, message = validate_get_request(request)

        self.assertFalse(valid)
        self.assertEqual(message, "Invalid attribute")


class TestExtractAndPrepareAttributesForGet(unittest.TestCase):
    def test_attributes_as_list(self):
        request = {"object_type": "artist", "attributes": ["name", "genre"]}
        expected = ("artist", {"name": True, "genre": True})
        self.assertEqual(extract_and_prepare_attributes_for_get(request), expected)

    def test_attributes_as_dict(self):
        request = {
            "object_type": "venue",
            "attributes": {"location": True, "capacity": False},
        }
        expected = ("venue", {"location": True, "capacity": False})
        self.assertEqual(extract_and_prepare_attributes_for_get(request), expected)

    def test_attributes_not_provided(self):
        request = {"object_type": "event"}
        expected = ("event", {})
        self.assertEqual(extract_and_prepare_attributes_for_get(request), expected)

    def test_empty_attributes_list(self):
        request = {"object_type": "ticket", "attributes": []}
        expected = ("ticket", {})
        self.assertEqual(extract_and_prepare_attributes_for_get(request), expected)

    def test_empty_attributes_dict(self):
        request = {"object_type": "attendee", "attributes": {}}
        expected = ("attendee", {})
        self.assertEqual(extract_and_prepare_attributes_for_get(request), expected)


class TestValidateQueriedAttributes(unittest.TestCase):
    # Setup for mock data
    attributes_schema = {
        "artist": ["name", "genre", "country"],
        "venue": ["location", "capacity"],
    }
    account_types = ["venue", "artist", "attendee"]
    non_account_types = ["event", "ticket"]

    @patch("main.attributes_schema", attributes_schema)
    @patch("main.account_types", account_types)
    @patch("main.non_account_types", non_account_types)
    def test_valid_queried_attributes(self):
        queried_attributes = {"name": True, "genre": True}
        object_type = "artist"
        self.assertTrue(validate_queried_attributes(queried_attributes, object_type)[0])

    def test_invalid_attribute_in_queried_attributes(self):
        queried_attributes = {"name": True, "invalid_attr": True}
        object_type = "artist"
        self.assertFalse(
            validate_queried_attributes(queried_attributes, object_type)[0]
        )

    def test_non_account_type_object(self):
        queried_attributes = {"name": True}
        object_type = "event"
        self.assertFalse(
            validate_queried_attributes(queried_attributes, object_type)[0]
        )

    def test_invalid_object_type(self):
        queried_attributes = {"name": True}
        object_type = "nonexistent_type"
        self.assertFalse(
            validate_queried_attributes(queried_attributes, object_type)[0]
        )

    def test_empty_queried_attributes(self):
        queried_attributes = {}
        object_type = "artist"
        self.assertFalse(
            validate_queried_attributes(queried_attributes, object_type)[0]
        )

    def test_queried_attribute_with_false_value(self):
        queried_attributes = {"name": False, "genre": True}
        object_type = "artist"
        self.assertFalse(
            validate_queried_attributes(queried_attributes, object_type)[0]
        )


class TestCreateAccount(unittest.TestCase):
    @patch("main.validate_request")
    @patch("main.supabase")
    def test_valid_request(self, mock_supabase, mock_validate):
        mock_validate.return_value = (True, "")
        mock_result = MagicMock()
        mock_result.data = [
            {
                "user_id": "12345",
                "email": "testartist@example.com",
                "username": "testartist",
                "genre": "Jazz",
            }
        ]
        mock_result.error = None
        mock_supabase.table().insert().execute.return_value = (
            ("data", [mock_result]),
            ("count", None),
        )

        user_id, message = create_account(
            {
                "function": "create",
                "object_type": "artist",
                "identifier": "testartist@example.com",
                "attributes": {
                    "email": "testartist@example.com",
                    "username": "testartist",
                    "genre": "Jazz",
                },
            }
        )

        # self.assertEqual(user_id, "12345")
        self.assertEqual(message, "Account creation was successful.")

    @patch("main.validate_request")
    def test_invalid_request(self, mock_validate):
        mock_validate.return_value = (False, "Invalid object type. Must be one of ['venue', 'artist', 'attendee'].")

        user_id, message = create_account(
            {
                "function": "create",
                "object_type": "invalid_type",
                "identifier": "testvenue@example.com",
                "attributes": {
                    "email": "testvenue@example.com",
                    "username": "testvenue",
                    "location": "Sample Location",
                },
            }
        )

        self.assertIsNone(user_id)
        self.assertEqual(
            message,
            "Invalid object type. Must be one of ['venue', 'artist', 'attendee'].",
        )

    @patch("main.validate_request")
    @patch("main.supabase")
    def test_exception_during_insert(self, mock_supabase, mock_validate):
        mock_validate.return_value = (True, "")
        mock_supabase.table().insert().execute.side_effect = Exception(
            "Database connection error"
        )

        user_id, message = create_account(
            {
                "function": "create",
                "object_type": "venue",
                "identifier": "1234456789101112",
                "attributes": {
                    "user_id": "1234456789101112",
                    "venue_name": "The Julius Bar",
                    "email": "testvenue@example.com",
                    "street_address": "1 Road Street",
                    "postcode": "AB1 2CD",
                    "city": "London",
                },
            }
        )

        self.assertIsNone(user_id)
        self.assertIn("An exception occurred", message)


class TestValidateCreateRequest(unittest.TestCase):
    @patch("main.extract_and_prepare_attributes")
    @patch("main.check_required_attributes")
    @patch("main.check_for_extra_attributes")
    def test_successful_validation(
        self, mock_check_extra, mock_check_required, mock_extract
    ):
        # Setup mock responses for a successful validation path
        mock_extract.return_value = ("artist", {"name": "John", "genre": "Rock"})
        mock_check_required.return_value = (True, "")
        mock_check_extra.return_value = (True, "")

        request = {
            "object_type": "artist",
            "attributes": {"name": "John", "genre": "Rock"},
        }
        valid, message = validate_create_request(request)

        self.assertTrue(valid)
        self.assertEqual(message, "Request is valid.")

    @patch("main.extract_and_prepare_attributes")
    @patch("main.check_required_attributes")
    def test_missing_required_attributes(self, mock_check_required, mock_extract):
        # Simulate missing required attributes
        mock_extract.return_value = ("artist", {"genre": "Rock"})
        mock_check_required.return_value = (False, "Missing required attributes.")

        request = {"object_type": "artist", "attributes": {"genre": "Rock"}}
        valid, message = validate_create_request(request)

        self.assertFalse(valid)
        self.assertEqual(message, "Missing required attributes.")

    @patch("main.extract_and_prepare_attributes")
    @patch("main.check_for_extra_attributes")
    def test_extra_undefined_attributes(self, mock_check_extra, mock_extract):
        mock_extract.return_value = (
            "artist",
            {
                "user_id": "123456789101112",
                "artist_name": "Jazzy Julius",
                "email": "user@example.com",
                "genres": "",
                "extra_attr": "Not Allowed",
            },
        )
        mock_check_extra.return_value = (
            False,
            "Additional, undefined attributes cannot be specified.",
        )

        request = {
            "object_type": "artist",
            "attributes": {"name": "John", "extra_attr": "Not Allowed"},
        }
        valid, message = validate_create_request(request)

        self.assertFalse(valid)
        self.assertEqual(
            message, "Additional, undefined attributes cannot be specified."
        )

    @patch("main.extract_and_prepare_attributes")
    def test_attributes_without_value(self, mock_extract):
        mock_extract.return_value = (
            "artist",
            {"user_id": "123456789101112", "artist_name": "Julius", "email": "user@example.com", "genres": "", "spotify_artist_id": "4a0SGxC38bo29VPaHtiFBf"},
        )

        request = {
            "function": "create",
            "object_type": "artist",
            "identifier": "123456789101112",
            "attributes": {
                "user_id": "123456789101112",
                "artist_name": "Julius",
                "email": "user@example.com",
                "genres": "",
                'spotify_artist_id': "4a0SGxC38bo29VPaHtiFBf"
            },
        }
        valid, message = validate_create_request(request)

        self.assertFalse(valid)
        self.assertEqual(message, "Every specified attribute must have a value.")


class TestUpdateAccount(unittest.TestCase):
    @patch("main.validate_request")
    @patch("main.supabase")
    def test_valid_update_request(self, mock_supabase, mock_validate):
        mock_validate.return_value = (True, "")
        mock_result = MagicMock()
        mock_result.error = None
        mock_result.data = [{"email": "new_email@example.com"}]
        mock_supabase.table().update().eq().execute.return_value = mock_result

        request = {
            "function": "update",
            "object_type": "artist",
            "identifier": "artist_id_123",
            "attributes": {"email": "new_email@example.com"},
        }
        success, message = update_account(request)

        self.assertTrue(success)
        self.assertEqual(message, "Account update was successful.")

    @patch("main.validate_request")
    def test_invalid_request_structure(self, mock_validate):
        mock_validate.return_value = (False, "Invalid request structure")

        request = {}  # Simulating an invalid request
        success, message = update_account(request)

        self.assertFalse(success)
        self.assertEqual(message, "Invalid request structure")

    @patch("main.validate_request")
    def test_no_valid_attributes_for_update(self, mock_validate):
        mock_validate.return_value = (True, "")

        request = {
            "object_type": "artist",
            "identifier": "artist_id_123",
            "attributes": {"email": None},  # No valid attributes to update
        }
        success, message = update_account(request)

        self.assertFalse(success)
        self.assertEqual(message, "No valid attributes provided for update.")

    @patch("main.validate_request")
    @patch("main.supabase")
    def test_supabase_update_error(self, mock_supabase, mock_validate):
        mock_validate.return_value = (True, "")
        mock_result = MagicMock()
        mock_result.error = (
            "Failed to update account: Attributes not updated as expected."
        )
        mock_supabase.table().update().eq().execute.return_value = mock_result

        request = {
            "object_type": "artist",
            "identifier": "artist_id_123",
            "attributes": {"username": "new_username"},
        }
        success, message = update_account(request)

        self.assertFalse(success)
        self.assertIn(
            "Failed to update account: Attributes not updated as expected.", message
        )

    @patch("main.validate_request")
    @patch("main.supabase")
    def test_exception_during_update_operation(self, mock_supabase, mock_validate):
        mock_validate.return_value = (True, "")
        mock_supabase.table().update().eq().execute.side_effect = Exception(
            "Database error"
        )

        request = {
            "object_type": "artist",
            "identifier": "artist_id_123",
            "attributes": {"genre": "new_genre"},
        }
        success, message = update_account(request)

        self.assertFalse(success)
        self.assertIn("An exception occurred: Database error", message)


class TestValidateUpdateRequest(unittest.TestCase):
    @patch("main.extract_and_prepare_attributes")
    @patch("main.check_for_extra_attributes")
    def test_valid_update_request(self, mock_check_extra, mock_extract):
        # Setup mock responses for a successful validation
        mock_extract.return_value = ("artist", {"name": "New Artist Name"})
        mock_check_extra.return_value = (True, "")

        request = {"object_type": "artist", "attributes": {"name": "New Artist Name"}}
        valid, message = validate_update_request(request)

        self.assertTrue(valid)
        self.assertEqual(message, "Request is valid.")

    @patch("main.extract_and_prepare_attributes")
    def test_no_attributes_specified_for_update(self, mock_extract):
        # Simulate no attributes provided for update
        mock_extract.return_value = ("artist", {})

        request = {"object_type": "artist", "attributes": {}}
        valid, message = validate_update_request(request)

        self.assertFalse(valid)
        self.assertEqual(
            message, "At least one attribute must be specified for update."
        )

    @patch("main.extract_and_prepare_attributes")
    @patch("main.check_for_extra_attributes")
    def test_extra_undefined_attributes_provided(self, mock_check_extra, mock_extract):
        # Simulate extra, undefined attributes provided
        mock_extract.return_value = ("artist", {"undefined_attr": "value"})
        mock_check_extra.return_value = (
            False,
            "Additional, undefined attributes cannot be specified.",
        )

        request = {"object_type": "artist", "attributes": {"undefined_attr": "value"}}
        valid, message = validate_update_request(request)

        self.assertFalse(valid)
        self.assertEqual(
            message, "Additional, undefined attributes cannot be specified."
        )

    @patch("main.extract_and_prepare_attributes")
    @patch("main.check_for_extra_attributes")
    def test_valid_request_with_multiple_attributes(
        self, mock_check_extra, mock_extract
    ):
        # Setup for a valid request with multiple attributes
        mock_extract.return_value = (
            "venue",
            {"location": "New Location", "capacity": 5000},
        )
        mock_check_extra.return_value = (True, "")

        request = {
            "object_type": "venue",
            "attributes": {"location": "New Location", "capacity": 5000},
        }
        valid, message = validate_update_request(request)

        self.assertTrue(valid)
        self.assertEqual(message, "Request is valid.")


class TestDeleteAccount(unittest.TestCase):
    @patch("main.validate_request")
    @patch("main.supabase")
    def test_valid_delete_request(self, mock_supabase, mock_validate):
        # Setup mock responses
        mock_validate.return_value = (True, "")
        mock_result = MagicMock()
        mock_result.data = {"deleted": 1}
        mock_result.error = None
        mock_supabase.table().delete().eq().execute.return_value = mock_result

        request = {
            "function": "delete",
            "object_type": "artist",
            "identifier": "artist_id_123",
        }
        success, message = delete_account(request)

        self.assertTrue(success)
        self.assertEqual(message, "Account deletion was successful.")

    @patch("main.validate_request")
    def test_invalid_request_structure(self, mock_validate):
        mock_validate.return_value = (False, "Invalid request structure")

        request = {}  # Simulating an invalid request
        success, message = delete_account(request)

        self.assertFalse(success)
        self.assertEqual(message, "Invalid request structure")

    @patch("main.validate_request")
    @patch("main.supabase")
    def test_supabase_delete_error(self, mock_supabase, mock_validate):
        mock_validate.return_value = (True, "")
        mock_result = MagicMock()
        # Simulate no rows being affected by the delete operation
        mock_result.data = []
        mock_supabase.table().delete().eq().execute.return_value = mock_result

        request = {
            "function": "delete",
            "object_type": "artist",
            "identifier": "artist_id_123",
        }
        success, message = delete_account(request)

        self.assertFalse(success)
        self.assertIn("Account not found or already deleted.", message)

    @patch("main.validate_request")
    @patch("main.supabase")
    def test_exception_during_delete_operation(self, mock_supabase, mock_validate):
        mock_validate.return_value = (True, "")
        mock_supabase.table().delete().eq().execute.side_effect = Exception(
            "Database error"
        )

        request = {
            "object_type": "artist",
            "identifier": "artist_id_123",
        }
        success, message = delete_account(request)

        self.assertFalse(success)
        self.assertIn("An exception occurred: Database error", message)


# class TestValidateDeleteRequest(unittest.TestCase):
# TBC when additional logic provided to make deletion more secure

if __name__ == "__main__":
    unittest.main()
