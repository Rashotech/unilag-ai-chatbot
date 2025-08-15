#!/bin/sh

# Write the Firebase credentials from the environment variable to a file
# This command checks if the secret is set before trying to write the file.
if [ -n "$FIREBASE_CREDENTIALS_JSON" ]; then
  echo "$FIREBASE_CREDENTIALS_JSON" > /code/firebase-adminsdk.json
  export FIREBASE_CREDENTIALS_PATH=/code/firebase-adminsdk.json
  echo "Firebase credentials file created."
fi

# Execute the original command passed to the container
exec "$@"