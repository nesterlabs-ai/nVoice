#!/bin/sh
set -e

# Backend URL from environment (the public URL for API calls)
# When behind Caddy, this should be the public domain
BACKEND_URL=${BACKEND_URL:-}

# If BACKEND_URL is empty, use relative URLs (Caddy will proxy)
if [ -z "$BACKEND_URL" ]; then
    BACKEND_URL=""
    echo "Backend URL: Using relative URLs (proxied by Caddy)"
else
    echo "Backend URL configured: ${BACKEND_URL}"
fi

# Create runtime config.js that sets window.__BACKEND_URL__
cat > /usr/share/nginx/html/config.js << EOF
window.__BACKEND_URL__ = "${BACKEND_URL}";
EOF

# Replace hardcoded localhost URLs in built JS files
if [ -n "$BACKEND_URL" ]; then
    find /usr/share/nginx/html -name '*.js' -exec sed -i "s|http://localhost:7860|${BACKEND_URL}|g" {} \; 2>/dev/null || true
    find /usr/share/nginx/html -name '*.js' -exec sed -i "s|https://localhost:7860|${BACKEND_URL}|g" {} \; 2>/dev/null || true
fi

exec "$@"
