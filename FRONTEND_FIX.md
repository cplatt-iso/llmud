# Frontend Build Fix - October 9, 2025

## Problem
The frontend was failing with 404 errors for `/src/main.jsx` because:
- The React + Vite app was being served as raw source files
- Nginx cannot serve JSX files directly
- The volume mount was overriding the container's built files

## Solution
Updated the frontend Dockerfile to use a multi-stage build:
1. **Stage 1 (Builder)**: Uses Node.js to install dependencies and build the app
2. **Stage 2 (Server)**: Uses Nginx to serve the built static files from `/app/dist`

Removed the volume mount from `docker-compose.yml` to allow the built files to be served.

## Production Use
```bash
docker compose up -d
```
This builds and serves the optimized production bundle.

## Development Use (with hot-reload)
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```
This uses Vite dev server with hot-reload. Access at http://localhost:5174

## Testing
After rebuild:
```bash
docker compose build frontend
docker compose up -d frontend
docker compose logs frontend --tail=20
```

No more 404 errors for JSX files! ✅
