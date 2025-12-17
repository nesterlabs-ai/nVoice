# Multi-User Voice Bot Deployment Summary

## Overview
The NesterConversationalBot has been successfully upgraded to support multiple concurrent users with proper session management and authentication.

## Changes Implemented

### 1. Server-Side Multi-User Support
- **File**: `app/core/connection_manager.py`
- **Status**: ✅ Created
- **Features**:
  - Session tracking with unique IDs
  - Capacity management (20 concurrent users max)
  - Heartbeat monitoring (30-second intervals)
  - Automatic cleanup on disconnect

### 2. FastAPI WebSocket Endpoint
- **File**: `app/api/websocket.py`
- **Status**: ✅ Updated
- **Changes**:
  - Integrated ConnectionManager
  - Each connection gets isolated VoiceAssistant instance
  - Unique session ID per user
  - Proper error handling and cleanup

### 3. Client-Side Connection Management
- **File**: `client/src/app.ts`
- **Status**: ✅ Updated
- **Changes**:
  - Added `isConnecting` state flag
  - Button state management (Connecting/Disconnect/Connect)
  - Race condition prevention
  - Better error handling

### 4. Docker Configuration
- **File**: `docker-compose.https.yml`
- **Status**: ✅ Updated
- **Changes**:
  - Switched to `fast_api` mode (from `websocket_server`)
  - Added `LIGHTRAG_API_KEY` environment variable
  - Port 7860 for all WebSocket connections

### 5. Caddy Reverse Proxy
- **File**: `Caddyfile`
- **Status**: ✅ Updated and added to repo
- **Changes**:
  - WebSocket routing to port 7860 (FastAPI)
  - Removed port 8765 references
  - Enhanced WebSocket configuration (keepalive, flush_interval)

### 6. GitHub Actions Deployment
- **File**: `.github/workflows/deploy.yml`
- **Status**: ✅ Updated
- **Changes**:
  - Auto-deploy on push to main branch
  - Sets `WEBSOCKET_SERVER=fast_api`
  - Adds `LIGHTRAG_API_KEY` to .env
  - Reloads Caddy configuration automatically

### 7. LightRAG Integration
- **File**: `app/services/rag.py`
- **Status**: ✅ Working
- **Authentication**: X-API-Key header
- **API URL**: http://16.170.172.18
- **Status**: 403 errors fixed by adding env variable to Docker

## Architecture

### WebSocket Mode: FastAPI (Port 7860)
```
User Browser → Caddy (443) → FastAPI (7860) → VoiceAssistant Instance
     ↓                            ↓
     ↓                      ConnectionManager
     ↓                            ↓
User Browser 2 → Caddy (443) → FastAPI (7860) → VoiceAssistant Instance 2
```

### Standalone WebSocket Server (Port 8765) - NOT USED
This mode is no longer active in the current deployment.

## Deployment Status

### Latest Commits
```
9a43b28 - Add LIGHTRAG_API_KEY to docker-compose environment
e2cbfee - setup the auth method of lightRag
b6dd3cb - Update Caddyfile to route WebSocket to FastAPI and add auto-reload
24496d1 - Fix multi-user connection issues and add capacity management
8fe8464 - Enable concurrent multi-user WebSocket connections
```

### GitHub Actions
- **Workflow**: `.github/workflows/deploy.yml`
- **Trigger**: Push to main branch
- **URL**: https://github.com/GURPREETKAURJETHRA/NESTER-AI-BOT/actions

## Verification Steps

### 1. Check Container Status
```bash
ssh -i ~/.ssh/LightsailDefaultKey-ap-south-1.pem ubuntu@3.6.64.48
cd nester-ai-bot
docker ps
```

Expected output:
```
CONTAINER ID   IMAGE                 STATUS         PORTS
xxxxx          nester-backend        Up X minutes   7860, 8765
xxxxx          nester-frontend       Up X minutes   80
xxxxx          caddy:2-alpine       Up X minutes   0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

### 2. Check Backend Logs
```bash
docker logs nester-backend --tail 50
```

Look for:
- `ConnectionManager initialized with max_sessions=20`
- `INFO: Application startup complete.`
- `Uvicorn running on http://0.0.0.0:7860`

### 3. Check Environment Variables
```bash
docker exec nester-backend env | grep -E "(WEBSOCKET_SERVER|LIGHTRAG_API_KEY)"
```

Expected:
```
WEBSOCKET_SERVER=fast_api
LIGHTRAG_API_KEY=805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f
```

### 4. Test Multi-User Connections

Open multiple browser tabs to: https://3-6-64-48.nip.io

**Tab 1**: Click Connect
- Should show "Connected" status
- Green status dot
- Voice overlay appears
- Logs show session ID

**Tab 2**: Click Connect (while Tab 1 is still connected)
- Should also show "Connected" status
- Tab 1 should remain connected (not disconnect)
- Each tab has different session ID

**Tab 3-20**: Repeat
- All tabs should remain connected simultaneously

**Tab 21**: Try to connect
- Should get rejection message: "Server at capacity (20 sessions)"

### 5. Test LightRAG Integration

During a voice conversation, ask: "What is AI?"

Backend logs should show:
```
[Session xxxx] RAG query: What is AI?
[Session xxxx] RAG response received
```

Should NOT show 403 errors.

### 6. Check Session Tracking

Backend logs during connections:
```
[Session a1b2c3d4] Connected. Active sessions: 1/20
[Session e5f6g7h8] Connected. Active sessions: 2/20
```

During disconnections:
```
[Session a1b2c3d4] Disconnected. Active sessions: 1/20
```

### 7. Test Heartbeat Monitoring

Keep a connection open for 30+ seconds. Backend logs should show:
```
[Session a1b2c3d4] Heartbeat ping sent
```

Every 30 seconds.

## Troubleshooting

### Issue: "Already connected or connection in progress"
**Cause**: Client-side race condition
**Fix**: Applied in client/src/app.ts with isConnecting flag
**Verify**: Check that button shows "Connecting..." and is disabled during connection

### Issue: Second user disconnects first user
**Cause**: Running in websocket_server mode instead of fast_api
**Fix**: Check WEBSOCKET_SERVER=fast_api in container environment
**Command**: `docker exec nester-backend env | grep WEBSOCKET_SERVER`

### Issue: WebSocket Error 1006
**Cause**: Caddyfile routing to wrong port
**Fix**: Caddyfile routes /ws to port 7860
**Verify**: `docker exec nester-caddy cat /etc/caddy/Caddyfile | grep -A 5 "handle /ws"`

### Issue: LightRAG 403 Errors
**Cause**: LIGHTRAG_API_KEY not in container environment
**Fix**: Added to docker-compose.https.yml
**Verify**: `docker exec nester-backend env | grep LIGHTRAG_API_KEY`

### Issue: Changes not deploying
**Cause**: GitHub Actions not running or Caddy not reloading
**Fix**: Check GitHub Actions workflow status
**URL**: https://github.com/GURPREETKAURJETHRA/NESTER-AI-BOT/actions

## Capacity Planning

### Current Limits
- **Max Sessions**: 20 concurrent users
- **Memory per Backend**: 400M limit, 200M reservation
- **Session Timeout**: 180 seconds
- **Heartbeat Interval**: 30 seconds

### Recommended Lightsail Instance
For 20 concurrent users: **2 GB RAM, 1 vCPU** (current setup)

For scaling to more users:
- 50 users: 4 GB RAM, 2 vCPU
- 100 users: 8 GB RAM, 4 vCPU

To increase capacity, edit `app/core/connection_manager.py`:
```python
connection_manager = ConnectionManager(max_sessions=50)  # Change from 20
```

## Access Information

- **Frontend URL**: https://3-6-64-48.nip.io
- **Backend Health**: https://3-6-64-48.nip.io/health
- **Session Status**: https://3-6-64-48.nip.io/status
- **Server IP**: 3.6.64.48 (ap-south-1)
- **LightRAG API**: http://16.170.172.18

## Files Modified

1. `/app/api/websocket.py` - ConnectionManager integration
2. `/app/core/connection_manager.py` - New session manager
3. `/client/src/app.ts` - Client state management
4. `/docker-compose.https.yml` - Environment and mode config
5. `/Caddyfile` - Reverse proxy routing
6. `/.github/workflows/deploy.yml` - Deployment automation
7. `/app/config/config.yaml` - LightRAG configuration
8. `/app/services/rag.py` - API key authentication

## Status: ✅ COMPLETE

All issues identified have been resolved:
- ✅ Multi-user concurrent connections working
- ✅ Session isolation and capacity management
- ✅ Automatic deployment via GitHub Actions
- ✅ LightRAG API authentication fixed
- ✅ WebSocket routing corrected
- ✅ Client-side race conditions prevented

Last deployment: Commit 9a43b28 (Add LIGHTRAG_API_KEY to docker-compose environment)
