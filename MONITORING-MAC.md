# Monitoring Guide for macOS

Complete guide to monitor your NesterVoiceAI deployment from macOS Terminal.

## Quick Start

### Step 1: Make Script Executable (One-time setup)

```bash
chmod +x monitor-mac.sh
```

### Step 2: Use the Commands

```bash
# Show help menu
./monitor-mac.sh help

# Check container status
./monitor-mac.sh status

# View backend logs
./monitor-mac.sh logs backend

# Follow live logs
./monitor-mac.sh follow

# Check for errors
./monitor-mac.sh errors

# Full diagnostic
./monitor-mac.sh full
```

## All Available Commands

### Logs

```bash
# Show all container logs (last 50 lines)
./monitor-mac.sh logs

# Show backend logs (last 50 lines)
./monitor-mac.sh logs backend

# Show backend logs (last 200 lines)
./monitor-mac.sh logs backend 200

# Show frontend logs
./monitor-mac.sh logs frontend

# Show Caddy proxy logs
./monitor-mac.sh logs caddy

# Follow backend logs in real-time (Ctrl+C to stop)
./monitor-mac.sh follow

# Follow frontend logs in real-time
./monitor-mac.sh follow frontend

# Show only errors
./monitor-mac.sh errors
```

### Status Checks

```bash
# Container status
./monitor-mac.sh status

# CPU/Memory usage
./monitor-mac.sh stats

# System memory
./monitor-mac.sh memory

# Backend health check
./monitor-mac.sh health
```

### Restart Containers

```bash
# Restart all containers
./monitor-mac.sh restart

# Restart backend only
./monitor-mac.sh restart backend

# Restart frontend only
./monitor-mac.sh restart frontend

# Restart Caddy only
./monitor-mac.sh restart caddy
```

### Diagnostics

```bash
# Full diagnostic report
./monitor-mac.sh full
```

## Common Tasks

### 1. Check if Everything is Running

```bash
./monitor-mac.sh status
```

Expected output:
```
NAME              IMAGE                  STATUS
nester-backend    ...                    Up 2 hours (healthy)
nester-frontend   ...                    Up 2 hours
nester-caddy      caddy:2-alpine         Up 2 hours
```

### 2. Debug Connection Issues

```bash
# Check backend logs
./monitor-mac.sh logs backend 100

# Check for errors
./monitor-mac.sh errors

# Check health
./monitor-mac.sh health
```

### 3. Monitor Live Activity

```bash
# Watch backend logs in real-time
./monitor-mac.sh follow
```

Press `Ctrl+C` to stop following.

### 4. Check Performance

```bash
./monitor-mac.sh stats
```

Expected output:
```
CONTAINER         CPU %   MEM USAGE / LIMIT
nester-backend    0.3%    240MB / 400MB
nester-frontend   0.0%    6MB / 50MB
nester-caddy      0.0%    20MB / 100MB
```

### 5. Restart After Changes

```bash
# Restart just backend
./monitor-mac.sh restart backend

# Restart everything
./monitor-mac.sh restart
```

## Advanced Usage

### Create Terminal Aliases

Add to your `~/.zshrc` or `~/.bash_profile`:

```bash
# Edit your profile
nano ~/.zshrc

# Add these lines:
alias nester-status='cd "/Users/apple/Desktop/nester ai bot opensource/NesterConversationalBot" && ./monitor-mac.sh status'
alias nester-logs='cd "/Users/apple/Desktop/nester ai bot opensource/NesterConversationalBot" && ./monitor-mac.sh logs backend'
alias nester-follow='cd "/Users/apple/Desktop/nester ai bot opensource/NesterConversationalBot" && ./monitor-mac.sh follow'
alias nester-errors='cd "/Users/apple/Desktop/nester ai bot opensource/NesterConversationalBot" && ./monitor-mac.sh errors'
alias nester-restart='cd "/Users/apple/Desktop/nester ai bot opensource/NesterConversationalBot" && ./monitor-mac.sh restart backend'
alias nester-health='cd "/Users/apple/Desktop/nester ai bot opensource/NesterConversationalBot" && ./monitor-mac.sh health'

# Save and reload
source ~/.zshrc
```

Then use from anywhere:
```bash
nester-status     # Show status
nester-logs       # Show logs
nester-follow     # Follow logs
nester-errors     # Show errors
nester-restart    # Restart backend
nester-health     # Health check
```

### Save Logs to File

```bash
# Save backend logs
./monitor-mac.sh logs backend 500 > backend-logs.txt

# Save errors
./monitor-mac.sh errors > errors.txt

# Save full diagnostic with timestamp
./monitor-mac.sh full > "diagnostic-$(date +%Y-%m-%d-%H%M).txt"
```

### Filter Logs

```bash
# Show only errors from backend
./monitor-mac.sh logs backend 200 | grep "ERROR"

# Show only Gemini-related logs
./monitor-mac.sh logs backend 200 | grep "Gemini\|GoogleLLM"

# Show connection logs
./monitor-mac.sh logs backend 100 | grep "connected\|disconnected"
```

## Troubleshooting

### SSH Connection Fails

```bash
# Check SSH key permissions (should be 600)
ls -l "LightsailDefaultKey-ap-south-1 (2).pem"

# Fix permissions if needed
chmod 600 "LightsailDefaultKey-ap-south-1 (2).pem"

# Test SSH connection
ssh -i "LightsailDefaultKey-ap-south-1 (2).pem" ec2-user@3.6.64.48 "echo 'Connected!'"
```

### Script Not Executable

```bash
# Make it executable
chmod +x monitor-mac.sh

# Verify
ls -l monitor-mac.sh
```

### See Full Error Messages

```bash
# Show more lines
./monitor-mac.sh logs backend 500

# Or follow live
./monitor-mac.sh follow
```

## Real-time Monitoring Dashboard

Create a monitoring loop:

```bash
# monitoring-loop.sh
#!/bin/bash

while true; do
    clear
    echo "=== NesterVoiceAI Live Monitor ==="
    echo "Press Ctrl+C to stop"
    echo ""

    ./monitor-mac.sh status
    echo ""
    ./monitor-mac.sh stats
    echo ""
    ./monitor-mac.sh health

    sleep 5
done
```

Make it executable and run:
```bash
chmod +x monitoring-loop.sh
./monitoring-loop.sh
```

## Log Analysis

### Find Specific Issues

```bash
# Find WebSocket errors
./monitor-mac.sh logs backend 500 | grep -i "WebSocket\|ws"

# Find memory issues
./monitor-mac.sh logs backend 500 | grep -i "memory\|OOM\|killed"

# Find API errors
./monitor-mac.sh logs backend 500 | grep -i "API\|404\|500\|error"

# Find Gemini errors
./monitor-mac.sh logs backend 500 | grep -i "Gemini\|Google"
```

### Count Issues

```bash
# Count errors in last 500 logs
./monitor-mac.sh logs backend 500 | grep "ERROR" | wc -l

# Count warnings
./monitor-mac.sh logs backend 500 | grep "WARNING" | wc -l
```

## Quick Reference Card

| Task | Command |
|------|---------|
| View backend logs | `./monitor-mac.sh logs backend` |
| Follow live logs | `./monitor-mac.sh follow` |
| Check status | `./monitor-mac.sh status` |
| See errors | `./monitor-mac.sh errors` |
| Restart backend | `./monitor-mac.sh restart backend` |
| Check resources | `./monitor-mac.sh stats` |
| Health check | `./monitor-mac.sh health` |
| Full diagnostic | `./monitor-mac.sh full` |

## Direct SSH Commands (Alternative)

If you prefer direct SSH commands:

```bash
# View status
ssh -i "LightsailDefaultKey-ap-south-1 (2).pem" ec2-user@3.6.64.48 "cd nester-bot && docker-compose -f docker-compose.https.yml ps"

# View backend logs
ssh -i "LightsailDefaultKey-ap-south-1 (2).pem" ec2-user@3.6.64.48 "cd nester-bot && docker-compose -f docker-compose.https.yml logs --tail=50 backend"

# Follow logs
ssh -i "LightsailDefaultKey-ap-south-1 (2).pem" ec2-user@3.6.64.48 "cd nester-bot && docker-compose -f docker-compose.https.yml logs -f backend"

# Health check
ssh -i "LightsailDefaultKey-ap-south-1 (2).pem" ec2-user@3.6.64.48 "curl -s http://localhost:7860/health"
```

## Notes

- All commands connect via SSH to your Lightsail instance
- Logs are fetched in real-time, no caching
- `follow` command shows live updates (press Ctrl+C to stop)
- Commands are safe - they only read data, never modify
- The script uses colored output for better readability
