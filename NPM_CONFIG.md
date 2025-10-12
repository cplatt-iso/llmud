# Nginx Proxy Manager Configuration for LLMUD

## Backend API & WebSocket Setup

The backend container (`mud_backend_service`) is accessible on the `npm_web` network at:
- **Hostname**: `mud_backend_service`
- **Port**: `8000`
- **Protocol**: HTTP (NPM handles HTTPS termination)

### NPM Proxy Host Configuration

#### 1. Main Proxy Host for llmud.trazen.org

**Details Tab:**
- Domain Names: `llmud.trazen.org`
- Scheme: `http`
- Forward Hostname/IP: `mud_frontend_service`
- Forward Port: `80`
- Cache Assets: ✓ (optional)
- Block Common Exploits: ✓
- Websockets Support: ✗ (not needed for main page)

**SSL Tab:**
- SSL Certificate: Your certificate
- Force SSL: ✓
- HTTP/2 Support: ✓

#### 2. WebSocket Path Configuration

You need to add a **Custom Location** to the main proxy host:

**Custom Location for /ws**
- Define location: `/ws`
- Scheme: `http`
- Forward Hostname/IP: `mud_backend_service`
- Forward Port: `8000`
- **Websockets Support: ✓** (CRITICAL!)

**Advanced Tab for /ws location:**
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

#### 3. API Endpoints (if needed)

If you want to proxy API calls separately:

**Custom Location for /api**
- Define location: `/api`
- Scheme: `http`
- Forward Hostname/IP: `mud_backend_service`
- Forward Port: `8000`
- Websockets Support: ✗

## Testing

### Test Backend Connectivity from NPM Container

```bash
# Get NPM container name
docker ps | grep nginx-proxy-manager

# Test connection (replace NPM_CONTAINER with actual name)
docker exec NPM_CONTAINER curl -v http://mud_backend_service:8000/
```

### Test WebSocket from Browser Console

```javascript
const ws = new WebSocket('wss://llmud.trazen.org/ws?token=YOUR_TOKEN&character_id=YOUR_CHAR_ID');
ws.onopen = () => console.log('Connected!');
ws.onmessage = (e) => console.log('Message:', e.data);
ws.onerror = (e) => console.error('Error:', e);
```

### Check Backend Logs

```bash
docker compose logs backend -f | grep -i "websocket\|upgrade\|/ws"
```

## Troubleshooting

### WebSocket Connection Fails (400/426/502)

1. **Ensure Websockets Support is enabled** in NPM for the `/ws` location
2. **Check proxy_http_version** is set to 1.1 in advanced config
3. **Verify Upgrade headers** are being passed through
4. **Check backend logs** for connection attempts

### 502 Bad Gateway

- Backend is not reachable from NPM
- Verify both containers are on `npm_web` network: `docker network inspect npm_web`
- Test connectivity: `docker exec NPM_CONTAINER curl http://mud_backend_service:8000/`

### Connection Timeout

- Check `proxy_read_timeout` is set high enough (86400 = 24 hours)
- Backend may be rejecting the connection (check auth token)

## Network Verification

```bash
# Verify both containers are on npm_web network
docker network inspect npm_web | jq '.[0].Containers'

# Should show both mud_backend_service and mud_frontend_service
```
