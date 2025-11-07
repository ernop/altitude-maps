# Deployment Configuration Template
# Copy this to deploy-config.ps1 and edit with your server details
# deploy-config.ps1 is gitignored

$REMOTE_HOST = "your-server.com"
$REMOTE_USER = "your-username"
$REMOTE_PATH = "/path/to/web/directory"

# SSH key (optional - leave empty to use default)
$SSH_KEY = ""

# Export for other scripts
$env:REMOTE_HOST = $REMOTE_HOST
$env:REMOTE_USER = $REMOTE_USER
$env:REMOTE_PATH = $REMOTE_PATH
$env:SSH_KEY = $SSH_KEY

Write-Host "Deployment configured:" -ForegroundColor Green
Write-Host "  Host: $REMOTE_HOST"
Write-Host "  User: $REMOTE_USER"
Write-Host "  Path: $REMOTE_PATH"

