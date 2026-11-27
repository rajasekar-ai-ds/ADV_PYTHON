import os

# Edit these, or set them as environment variables before running.
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "@raj618240#.")
MYSQL_DB = os.environ.get("MYSQL_DB", "ebms")

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")

BILL_DUE_DAYS = 15  # due date = bill date + 15 days
