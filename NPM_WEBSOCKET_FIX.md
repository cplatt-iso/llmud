# Quick NPM WebSocket Fix

## Problem
Frontend can't connect to WebSocket at `wss://llmud.trazen.org/ws`

## Solution
Configure NPM to proxy WebSocket connections to the backend.

## NPM Configuration Steps

### Option 1: Add Custom Location (Recommended)

**IMPORTANT:** You must **DISABLE** WebSocket support on the main proxy host, then enable it only for the `/ws` location!

1. Open your **llmud.trazen.org** Proxy Host in NPM
2. On the **Details** tab, ensure **"Websockets Support"** is **DISABLED** (unchecked)
3. Go to **Custom Locations** tab
4. Click **Add location**
5. Configure:
   - **Define location**: `/ws`
   - **Scheme**: `http`
   - **Forward Hostname / IP**: `mud_backend_service`
   - **Forward Port**: `8000`
   - **Websockets Support**: ✓ **ENABLE THIS!** (only for this location)
   
5. Click the **gear icon** next to the location to add **Advanced** config:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_read_timeout 86400;
```

6. Save everything

### Option 2: Separate Proxy Host (Alternative)

Create a NEW proxy host:
- **Domain**: `llmud.trazen.org` (same)
- **Forward to**: `http://mud_backend_service:8000`
- **Websockets**: ✓ ENABLE
- **Path**: Add `/ws` as custom location

## Testing

### From Browser Console (once logged in)
```javascript
// Check if WS is trying to connect
// Open browser console on llmud.trazen.org and look for WebSocket errors
```

### Check Backend Logs
```bash
docker compose logs backend -f
```

You should see WebSocket connection messages when a player logs in.

### Test NPM -> Backend Connectivity
```bash
# This should work (already tested)
docker exec npm curl -s http://mud_backend_service:8000/
```

## Common Issues

**426 Upgrade Required / 400 Bad Request**
- WebSocket support not enabled in NPM
- Missing Upgrade headers

**502 Bad Gateway**
- Backend not reachable (but we verified it is)
- Wrong hostname/port in NPM config

**Connection timeout**
- `proxy_read_timeout` too low
- Firewall blocking WebSocket

## Network Info
- Backend container: `mud_backend_service` on `172.19.0.5`
- NPM container: `npm` on `172.19.0.7`  
- Frontend container: `mud_frontend_service` on `172.19.0.10`
- All on `npm_web` network ✓

## What the Frontend Expects
Frontend connects to: `wss://llmud.trazen.org/ws?token=XXX&character_id=YYY`

NPM needs to:
1. Accept the secure WebSocket connection (wss://)
2. Upgrade the HTTP connection to WebSocket
3. Forward to `http://mud_backend_service:8000/ws` (ws:// over http internally)
4. Keep the connection alive (don't timeout)
