# Monitoring Guide for Windows PowerShell

Complete guide to monitor your NesterVoiceAI deployment from Windows.

## Setup

### 1. Prerequisites

Ensure you have:
- PowerShell 5.1+ (comes with Windows 10/11)
- SSH client (comes with Windows 10+)
- The SSH key file: `LightsailDefaultKey-ap-south-1 (2).pem`

### 2. Place SSH Key

Put the SSH key in the project directory or update the path in the scripts.

### 3. Test SSH Connection

```powershell
ssh -i "LightsailDefaultKey-ap-south-1 (2).pem" ec2-user@3.6.64.48 "echo 'Connected!'"
```

## Quick Start

### Method 1: Quick Commands (Recommended)

Load the quick commands:

```powershell
. .\quick-commands.ps1
```

Then use simple commands:

```powershell
# View logs
Show-BackendLogs          # Last 50 backend logs
Show-BackendLogs 200      # Last 200 logs
Show-FrontendLogs         # Frontend logs
Show-CaddyLogs            # Caddy proxy logs
Show-AllLogs              # All container logs
Show-Errors               # Only errors

# Follow live logs
Follow-BackendLogs        # Live backend logs (Ctrl+C to stop)

# Status checks
Show-Status               # Container status
Show-Stats                # CPU/Memory usage
Show-Memory               # System memory
Check-Health              # Backend health

# Restart
Restart-Backend           # Restart backend only
Restart-All               # Restart all containers

# Help
Show-Menu                 # Show command list
```

### Method 2: Monitor Script

```powershell
# Basic usage
.\monitor.ps1 -Command status
.\monitor.ps1 -Command logs -Service backend
.\monitor.ps1 -Command health
.\monitor.ps1 -Command errors
.\monitor.ps1 -Command full

# All commands
.\monitor.ps1 -Command help
```

## Common Tasks

### 1. Check if Everything is Running

```powershell
. .\quick-commands.ps1
Show-Status
```

Expected output:
```
NAME              IMAGE                  STATUS
nester-backend    ...                    Up 2 hours (healthy)
nester-frontend   ...                    Up 2 hours
nester-caddy      caddy:2-alpine         Up 2 hours
```

### 2. Debug Connection Issues

```powershell
# Check backend logs
Show-BackendLogs 100

# Check for errors
Show-Errors

# Check health
Check-Health
```

### 3. Monitor Live Activity

```powershell
# Watch backend logs in real-time
Follow-BackendLogs
```

Press `Ctrl+C` to stop following.

### 4. Check Performance

```powershell
Show-Stats
```

Expected output:
```
CONTAINER         CPU %   MEM USAGE / LIMIT
nester-backend    0.3%    240MB / 400MB
nester-frontend   0.0%    6MB / 50MB
nester-caddy      0.0%    20MB / 100MB
```

### 5. View Specific Service Logs

```powershell
# Backend (Python/FastAPI/Pipecat)
Show-BackendLogs 100

# Frontend (Nginx/React)
Show-FrontendLogs 50

# Reverse Proxy (Caddy)
Show-CaddyLogs 50

# Everything
Show-AllLogs 30
```

### 6. Restart After Changes

```powershell
# Restart just backend
Restart-Backend

# Restart everything
Restart-All
```

## Advanced Usage

### Create Aliases

Add to your PowerShell profile (`$PROFILE`):

```powershell
# Edit profile
notepad $PROFILE

# Add these lines:
function nb { . "C:\path\to\project\quick-commands.ps1"; Show-BackendLogs @args }
function ns { . "C:\path\to\project\quick-commands.ps1"; Show-Status }
function ne { . "C:\path\to\project\quick-commands.ps1"; Show-Errors }
function nr { . "C:\path\to\project\quick-commands.ps1"; Restart-Backend }
```

Then use:
```powershell
nb 200    # Show 200 backend logs
ns        # Show status
ne        # Show errors
nr        # Restart backend
```

### Save Logs to File

```powershell
# Save backend logs
Show-BackendLogs 500 | Out-File -FilePath "backend-logs.txt"

# Save errors
Show-Errors | Out-File -FilePath "errors.txt"

# Save full diagnostic
.\monitor.ps1 -Command full | Out-File -FilePath "diagnostic-$(Get-Date -Format 'yyyy-MM-dd-HHmm').txt"
```

### Filter Logs

```powershell
# Show only errors from backend
Show-BackendLogs 200 | Select-String "ERROR"

# Show only Gemini-related logs
Show-BackendLogs 200 | Select-String "Gemini|GoogleLLM"

# Show connection logs
Show-BackendLogs 100 | Select-String "connected|disconnected"
```

## Troubleshooting

### SSH Connection Fails

```powershell
# Check SSH key permissions
icacls "LightsailDefaultKey-ap-south-1 (2).pem"

# Fix permissions (remove inheritance, keep only your user)
icacls "LightsailDefaultKey-ap-south-1 (2).pem" /inheritance:r
icacls "LightsailDefaultKey-ap-south-1 (2).pem" /grant:r "$env:USERNAME:(R)"
```

### Commands Don't Work

```powershell
# Reload quick commands
. .\quick-commands.ps1

# Or restart PowerShell
```

### See Full Error Messages

```powershell
# Use monitor.ps1 for detailed output
.\monitor.ps1 -Command logs -Service backend

# Or show more lines
Show-BackendLogs 500
```

## Real-time Monitoring Dashboard

Create a monitoring loop:

```powershell
# monitoring-loop.ps1
. .\quick-commands.ps1

while ($true) {
    Clear-Host
    Write-Host "=== NesterVoiceAI Live Monitor ===" -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Yellow

    Show-Status
    Write-Host ""
    Show-Stats
    Write-Host ""
    Check-Health

    Start-Sleep -Seconds 5
}
```

Run it:
```powershell
.\monitoring-loop.ps1
```

## Log Analysis

### Find Specific Issues

```powershell
# Find WebSocket errors
Show-BackendLogs 500 | Select-String "WebSocket|ws"

# Find memory issues
Show-BackendLogs 500 | Select-String "memory|OOM|killed"

# Find API errors
Show-BackendLogs 500 | Select-String "API|404|500|error"

# Find Gemini errors
Show-BackendLogs 500 | Select-String "Gemini|Google"
```

### Count Issues

```powershell
# Count errors in last 500 logs
(Show-BackendLogs 500 | Select-String "ERROR").Count

# Count warnings
(Show-BackendLogs 500 | Select-String "WARNING").Count
```

## Quick Reference Card

| Task | Command |
|------|---------|
| View backend logs | `Show-BackendLogs` |
| Follow live logs | `Follow-BackendLogs` |
| Check status | `Show-Status` |
| See errors | `Show-Errors` |
| Restart backend | `Restart-Backend` |
| Check resources | `Show-Stats` |
| Health check | `Check-Health` |
| Full diagnostic | `.\monitor.ps1 -Command full` |

## Notes

- All commands connect via SSH to your Lightsail instance
- Logs are fetched in real-time, no caching
- `Follow-BackendLogs` shows live updates (press Ctrl+C to stop)
- Commands are safe - they only read data, never modify
