#!/bin/bash
# Altitude Maps - Production Deployment Script
# Deploys only the web viewer and generated data (no raw data or processing code)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
REMOTE_HOST=""
REMOTE_PATH=""
REMOTE_USER=""
DRY_RUN=false

show_usage() {
    echo "Usage: $0 -h HOST -p PATH [-u USER] [-d]"
    echo ""
    echo "Options:"
    echo "  -h HOST     Remote host (required)"
    echo "  -p PATH     Remote path (required)"
    echo "  -u USER     Remote user (optional)"
    echo "  -d          Dry run (no changes)"
    echo ""
    echo "Example:"
    echo "  $0 -h example.com -p /var/www/altitude-maps -u deploy"
    echo "  $0 -h 192.168.1.100 -p /home/user/www -d"
    exit 1
}

while getopts "h:p:u:d" opt; do
    case $opt in
        h) REMOTE_HOST="$OPTARG" ;;
        p) REMOTE_PATH="$OPTARG" ;;
        u) REMOTE_USER="$OPTARG" ;;
        d) DRY_RUN=true ;;
        *) show_usage ;;
    esac
done

if [ -z "$REMOTE_HOST" ] || [ -z "$REMOTE_PATH" ]; then
    echo -e "${RED}Error: Host and path are required${NC}"
    show_usage
fi

# Build destination
if [ -n "$REMOTE_USER" ]; then
    DESTINATION="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"
else
    DESTINATION="${REMOTE_HOST}:${REMOTE_PATH}"
fi

# Header
echo -e "${CYAN}=======================================================================${NC}"
echo -e "${CYAN}Altitude Maps - Production Deployment${NC}"
echo -e "${CYAN}=======================================================================${NC}"

echo -e "\n${YELLOW}Deployment Configuration:${NC}"
echo -e "  Local:  ${GREEN}$(pwd)${NC}"
echo -e "  Remote: ${GREEN}${DESTINATION}${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "  Mode:   ${YELLOW}DRY RUN (no changes will be made)${NC}"
else
    echo -e "  Mode:   ${RED}LIVE DEPLOYMENT${NC}"
fi

echo -e "\n${YELLOW}Files to deploy:${NC}"
echo "  [x] HTML viewers (interactive_viewer_advanced.html, viewer.html)"
echo "  [x] JavaScript (js/)"
echo "  [x] CSS (css/)"
echo "  [x] Generated data (generated/)"
echo "  [x] README.md (optional)"
echo ""
echo "  Note: External dependencies loaded from CDN (Three.js, jQuery, Select2)"

echo -e "\n${YELLOW}Files excluded:${NC}"
echo "  [-] Raw data (data/) - NOT NEEDED for viewer"
echo "  [-] Source code (src/) - NOT NEEDED for viewer"
echo "  [-] Processing scripts (*.py) - NOT NEEDED for viewer"
echo "  [-] Virtual environment (venv/)"
echo "  [-] Documentation (tech/, learnings/)"
echo "  [-] Development files"

# Check for rsync
if ! command -v rsync &> /dev/null; then
    echo -e "\n${RED}[X] Error: rsync not found!${NC}"
    echo -e "${YELLOW}    Install rsync:${NC}"
    echo -e "${NC}    - Ubuntu/Debian: sudo apt-get install rsync${NC}"
    echo -e "${NC}    - macOS: brew install rsync${NC}"
    echo -e "${NC}    - RHEL/CentOS: sudo yum install rsync${NC}"
    exit 1
fi

echo -e "\n${CYAN}=======================================================================${NC}"

# Confirm if not dry run
if [ "$DRY_RUN" = false ]; then
    echo -e "\n${YELLOW}This will upload files to the remote server.${NC}"
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Deployment cancelled."
        exit 0
    fi
fi

echo -e "\n${GREEN}[*] Starting deployment...${NC}"

# Build rsync arguments
RSYNC_ARGS=(
    -avz                        # archive, verbose, compress
    --progress                  # show progress
    --delete                    # delete remote files not in source
    --include="interactive_viewer_advanced.html"
    --include="viewer.html"
    --include="js/"
    --include="js/***"
    --include="css/"
    --include="css/***"
    --include="generated/"
    --include="generated/***"
    --include="README.md"
    --exclude="*"               # exclude everything else
    --exclude=".*"              # exclude hidden files
    --exclude="__pycache__/"    # exclude Python cache
    --exclude="*.pyc"           # exclude compiled Python
    --exclude="data/"           # exclude raw data
    --exclude="src/"            # exclude source code
    --exclude="venv/"           # exclude virtual environment
    --exclude="output/"         # exclude output images
    --exclude="rasters/"        # exclude rasters
    --exclude="tech/"           # exclude technical docs
    --exclude="learnings/"      # exclude learning docs
    --exclude="*.py"            # exclude Python scripts (except serve_viewer.py)
    --exclude="*.ps1"           # exclude PowerShell scripts
    --exclude="*.sh"            # exclude shell scripts
    --exclude="*.txt"           # exclude text files
    --exclude="*.md"            # exclude markdown (except README.md)
    --exclude="*.log"           # exclude logs
    --exclude="*.png"           # exclude screenshots
    --exclude=".git/"           # exclude git
    --exclude=".gitignore"      # exclude gitignore
)

if [ "$DRY_RUN" = true ]; then
    RSYNC_ARGS+=(--dry-run)
fi

# Add source and destination
RSYNC_ARGS+=("$(pwd)/")
RSYNC_ARGS+=("$DESTINATION")

# Execute rsync
echo -e "\n${CYAN}[*] Running rsync...${NC}"
echo -e "${NC}Command: rsync ${RSYNC_ARGS[*]}${NC}"
echo ""

rsync "${RSYNC_ARGS[@]}"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=======================================================================${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${GREEN}[✓] Dry run completed successfully!${NC}"
        echo -e "${YELLOW}    Run without -d to perform actual deployment${NC}"
    else
        echo -e "${GREEN}[✓] Deployment completed successfully!${NC}"
        echo -e "\n${YELLOW}Viewer deployed to: ${REMOTE_PATH}${NC}"
        echo -e "  ${NC}Your web server should now serve:${NC}"
        echo -e "  ${CYAN}- ${REMOTE_PATH}/interactive_viewer_advanced.html (main viewer)${NC}"
        echo -e "  ${CYAN}- ${REMOTE_PATH}/viewer.html (simple viewer)${NC}"
        echo -e "\n  ${GREEN}All files use relative paths - no additional config needed!${NC}"
    fi
    echo -e "${GREEN}=======================================================================${NC}"
else
    echo -e "\n${RED}[X] Deployment failed with exit code: $?${NC}"
    exit 1
fi

