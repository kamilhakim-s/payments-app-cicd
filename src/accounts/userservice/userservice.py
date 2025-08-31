# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Userservice manages user account creation, user login, and related tasks
"""

import atexit
from datetime import datetime, timedelta, timezone
import logging
import os
import sys
import re

import bcrypt
import jwt
from flask import Flask, jsonify, request
import bleach
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.propagate import set_global_textmap
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from db import UserDb

# Constants for error messages
ERROR_CREATING_USER = "Error creating new user: %s"
ERROR_LOGGING_IN = "Error logging in: %s"


def _configure_app(app):
    """Configure Flask app settings"""
    app.config["VERSION"] = os.environ.get("VERSION")
    app.config["EXPIRY_SECONDS"] = int(os.environ.get("TOKEN_EXPIRY_SECONDS"))
    app.config["PRIVATE_KEY"] = open(os.environ.get("PRIV_KEY_PATH"), "r").read()
    app.config["PUBLIC_KEY"] = open(os.environ.get("PUB_KEY_PATH"), "r").read()


def _setup_database(app):
    """Configure database connection"""
    try:
        users_db = UserDb(os.environ.get("ACCOUNTS_DB_URI"), app.logger)
        return users_db
    except OperationalError:
        app.logger.critical("users_db database connection failed")
        sys.exit(1)


def _setup_logging(app):
    """Setup logging configuration"""
    app.logger.handlers = logging.getLogger("gunicorn.error").handlers
    app.logger.setLevel(logging.getLogger("gunicorn.error").level)
    app.logger.info("Starting userservice.")


def _setup_tracing(app):
    """Setup tracing configuration"""
    if os.environ["ENABLE_TRACING"] == "true":
        app.logger.info("✅ Tracing enabled.")
        trace.set_tracer_provider(TracerProvider())
        cloud_trace_exporter = CloudTraceSpanExporter()
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(cloud_trace_exporter))
        set_global_textmap(CloudTraceFormatPropagator())
        FlaskInstrumentor().instrument_app(app)
    else:
        app.logger.info("🚫 Tracing disabled.")


def _validate_new_user(req):
    """Validate new user request data"""
    # Check if required fields are filled
    fields = (
        "username",
        "password",
        "password-repeat",
        "firstname",
        "lastname",
        "birthday",
        "timezone",
        "address",
        "state",
        "zip",
        "ssn",
    )
    if any(f not in req for f in fields):
        raise UserWarning("missing required field(s)")
    if any(not bool(req[f] or req[f].strip()) for f in fields):
        raise UserWarning("missing value for input field(s)")

    # Verify username contains only 2-15 alphanumeric or underscore characters
    if not re.match(r"\A\w{2,15}\Z", req["username"]):
        raise UserWarning("username must contain 2-15 alphanumeric characters or underscores")
    # Check if passwords match
    if req["password"] != req["password-repeat"]:
        raise UserWarning("passwords do not match")


def _create_user_handler(app, users_db):
    """Create user route handler"""

    def create_user():
        """Create a user record.

        Fails if that username already exists.

        Generates a unique accountid.

        request fields:
        - username
        - password
        - password-repeat
        - firstname
        - lastname
        - birthday
        - timezone
        - address
        - state
        - zip
        - ssn
        """
        try:
            app.logger.debug("Sanitizing input.")
            req = {k: bleach.clean(v) for k, v in request.form.items()}
            _validate_new_user(req)
            # Check if user already exists
            if users_db.get_user(req["username"]) is not None:
                raise NameError("user {} already exists".format(req["username"]))

            # Create password hash with salt
            app.logger.debug("Creating password hash.")
            password = req["password"]
            salt = bcrypt.gensalt()
            passhash = bcrypt.hashpw(password.encode("utf-8"), salt)

            accountid = users_db.generate_accountid()

            # Create user data to be added to the database
            user_data = {
                "accountid": accountid,
                "username": req["username"],
                "passhash": passhash,
                "firstname": req["firstname"],
                "lastname": req["lastname"],
                "birthday": req["birthday"],
                "timezone": req["timezone"],
                "address": req["address"],
                "state": req["state"],
                "zip": req["zip"],
                "ssn": req["ssn"],
            }
            # Add user_data to database
            app.logger.debug("Adding user to the database")
            users_db.add_user(user_data)
            app.logger.info("Successfully created user.")

        except UserWarning as warn:
            app.logger.error(ERROR_CREATING_USER, str(warn))
            return str(warn), 400
        except NameError as err:
            app.logger.error(ERROR_CREATING_USER, str(err))
            return str(err), 409
        except SQLAlchemyError as err:
            app.logger.error(ERROR_CREATING_USER, str(err))
            return "failed to create user", 500

        return jsonify({}), 201

    return create_user


def _login_handler(app, users_db):
    """Login route handler"""

    def login():
        """Login a user and return a JWT token

        Fails if username doesn't exist or password doesn't match hash

        token expiry time determined by environment variable

        request fields:
        - username
        - password
        """
        app.logger.debug("Sanitizing login input.")
        username = bleach.clean(request.args.get("username"))
        password = bleach.clean(request.args.get("password"))

        # Get user data
        try:
            app.logger.debug("Getting the user data.")
            user = users_db.get_user(username)
            if user is None:
                raise LookupError("user {} does not exist".format(username))

            # Validate the password
            app.logger.debug("Validating the password.")
            if not bcrypt.checkpw(password.encode("utf-8"), user["passhash"]):
                raise PermissionError("invalid login")

            full_name = "{} {}".format(user["firstname"], user["lastname"])
            exp_time = datetime.now(timezone.utc) + timedelta(seconds=app.config["EXPIRY_SECONDS"])
            payload = {
                "user": username,
                "acct": user["accountid"],
                "name": full_name,
                "iat": datetime.now(timezone.utc),
                "exp": exp_time,
            }
            app.logger.debug("Creating jwt token.")
            token = jwt.encode(payload, app.config["PRIVATE_KEY"], algorithm="RS256")
            app.logger.info("Login Successful.")
            return jsonify({"token": token}), 200

        except LookupError as err:
            app.logger.error(ERROR_LOGGING_IN, str(err))
            return str(err), 404
        except PermissionError as err:
            app.logger.error(ERROR_LOGGING_IN, str(err))
            return str(err), 401
        except SQLAlchemyError as err:
            app.logger.error(ERROR_LOGGING_IN, str(err))
            return "failed to retrieve user information", 500

    return login


def _register_routes(app, users_db):
    """Register all route handlers"""
    # Disabling unused-variable for lines with route decorated functions
    # as pylint thinks they are unused
    # pylint: disable=unused-variable

    @app.route("/version", methods=["GET"])
    def version():
        """Service version endpoint"""
        return app.config["VERSION"], 200

    @app.route("/ready", methods=["GET"])
    def readiness():
        """Readiness probe"""
        return "ok", 200

    # Register complex route handlers
    app.route("/users", methods=["POST"])(_create_user_handler(app, users_db))
    app.route("/login", methods=["GET"])(_login_handler(app, users_db))

    @atexit.register
    def _shutdown():
        """Executed when web app is terminated."""
        app.logger.info("Stopping userservice.")


def create_app():
    """Flask application factory to create instances
    of the Userservice Flask App
    """
    app = Flask(__name__)

    # Setup logging first
    _setup_logging(app)

    # Configure app settings
    _configure_app(app)

    # Setup tracing
    _setup_tracing(app)

    # Setup database connection
    users_db = _setup_database(app)

    # Register routes
    _register_routes(app, users_db)

    return app


if __name__ == "__main__":
    # Create an instance of flask server when called directly
    USERSERVICE = create_app()
    USERSERVICE.run()
