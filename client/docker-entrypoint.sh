#!/bin/sh
set -e

# Backend URL from environment (should be public HTTPS URL)
BACKEND_URL=${BACKEND_URL:-https://localhost}

# Replace environment variables in nginx config
envsubst '${BACKEND_URL}' < /etc/nginx/conf.d/default.conf > /etc/nginx/conf.d/default.conf.tmp
mv /etc/nginx/conf.d/default.conf.tmp /etc/nginx/conf.d/default.conf

# Create runtime config.js that sets window.__BACKEND_URL__
# This is loaded before the main app and provides the correct URL
cat > /usr/share/nginx/html/config.js << EOF
window.__BACKEND_URL__ = "${BACKEND_URL}";
EOF

# Also replace hardcoded URLs in built JS as fallback
find /usr/share/nginx/html -name '*.js' -exec sed -i "s|http://localhost:7860|${BACKEND_URL}|g" {} \;
find /usr/share/nginx/html -name '*.js' -exec sed -i "s|http://backend:7860|${BACKEND_URL}|g" {} \;

echo "Backend URL configured: ${BACKEND_URL}"

exec "$@"
