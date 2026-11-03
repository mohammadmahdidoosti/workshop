#!/bin/sh
# Builds the password file from environment variables set in Coolify.
# Fails closed: without a password the container does not start, so the data is never public.
set -e
USER_NAME="${BASIC_AUTH_USER:-caravan}"
if [ -z "$BASIC_AUTH_PASSWORD" ]; then
  echo "BASIC_AUTH_PASSWORD is not set - refusing to start" >&2
  exit 1
fi
htpasswd -bcB /etc/nginx/.htpasswd "$USER_NAME" "$BASIC_AUTH_PASSWORD" >/dev/null 2>&1
echo "basic auth enabled for user $USER_NAME"
