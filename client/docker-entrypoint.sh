#!/bin/sh
set -e

# Backend URL from environment (should be public HTTPS URL)
BACKEND_URL=${BACKEND_URL:-https://localhost}

# Replace environment variables in nginx config
envsubst '${BACKEND_URL}' < /etc/nginx/conf.d/default.conf > /etc/nginx/conf.d/default.conf.tmp
mv /etc/nginx/conf.d/default.conf.tmp /etc/nginx/conf.d/default.conf

# Inject backend URL into the built JavaScript (for client-side API calls)
# Replace all possible hardcoded URLs with the correct public URL
find /usr/share/nginx/html -name '*.js' -exec sed -i "s|http://localhost:7860|${BACKEND_URL}|g" {} \;
find /usr/share/nginx/html -name '*.js' -exec sed -i "s|http://backend:7860|${BACKEND_URL}|g" {} \;

echo "Backend URL configured: ${BACKEND_URL}"

exec "$@"
