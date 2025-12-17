#!/bin/bash

################################################################################
# setup_git.sh - Git Repository Setup on Server
#
# Sets up git repository on the VPS server for automated deployment
# Configures git user, remotes, SSH keys, and git hooks directory
################################################################################

set -e  # Exit on any error

# === Configuration ===
REPO_PATH="${1:-.}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-agent@server-agent.local}"
GIT_USER_NAME="${GIT_USER_NAME:-Server Agent vNext}"
GITHUB_REMOTE="${GITHUB_REMOTE:-origin}"
GITHUB_URL="${GITHUB_URL:-}"

# === Colors for output ===
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

# === Logging functions ===
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# === Check if git is installed ===
if ! command -v git &> /dev/null; then
    log_error "git is not installed"
    exit 1
fi

log_info "Setting up git repository in $REPO_PATH"

# === Initialize git repository if needed ===
if [ ! -d "$REPO_PATH/.git" ]; then
    log_info "Initializing git repository..."
    cd "$REPO_PATH"
    git init
    log_success "Git repository initialized"
else
    log_info "Git repository already exists"
    cd "$REPO_PATH"
fi

# === Configure git user ===
log_info "Configuring git user..."
git config user.email "$GIT_USER_EMAIL" || log_warning "Failed to set git user email"
git config user.name "$GIT_USER_NAME" || log_warning "Failed to set git user name"
log_success "Git user configured: $GIT_USER_NAME <$GIT_USER_EMAIL>"

# === Configure git remotes ===
if [ -n "$GITHUB_URL" ]; then
    log_info "Configuring remote: $GITHUB_REMOTE"

    # Check if remote already exists
    if git remote get-url "$GITHUB_REMOTE" &> /dev/null; then
        log_info "Remote '$GITHUB_REMOTE' already exists, updating URL..."
        git remote set-url "$GITHUB_REMOTE" "$GITHUB_URL"
    else
        log_info "Adding remote '$GITHUB_REMOTE'..."
        git remote add "$GITHUB_REMOTE" "$GITHUB_URL"
    fi
    log_success "Remote configured: $GITHUB_URL"
else
    log_warning "GITHUB_URL not provided, skipping remote configuration"
fi

# === Set up SSH key for push/pull ===
SSH_KEY_PATH="${HOME}/.ssh/id_ed25519"
SSH_KEY_PUB="${SSH_KEY_PATH}.pub"

if [ ! -f "$SSH_KEY_PATH" ]; then
    log_info "Generating SSH key for git operations..."
    mkdir -p "$(dirname "$SSH_KEY_PATH")"
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N "" -C "server-agent-vnext@$(hostname)" || log_error "Failed to generate SSH key"
    log_success "SSH key generated: $SSH_KEY_PATH"

    if [ -f "$SSH_KEY_PUB" ]; then
        log_warning "Please add this public key to your GitHub account:"
        log_warning "================================================"
        cat "$SSH_KEY_PUB"
        log_warning "================================================"
    fi
else
    log_info "SSH key already exists: $SSH_KEY_PATH"
fi

# === Configure SSH for git operations ===
log_info "Configuring SSH for git..."
git config core.sshCommand "ssh -i $SSH_KEY_PATH" || log_warning "Failed to set SSH command"
log_success "SSH configured for git operations"

# === Set up git hooks directory ===
log_info "Setting up git hooks directory..."
HOOKS_DIR="$REPO_PATH/.git/hooks"
POST_RECEIVE_HOOK="$HOOKS_DIR/post-receive"

# Ensure hooks directory exists
mkdir -p "$HOOKS_DIR"

# Create post-receive hook if deploying from a bare repo
if [ ! -f "$POST_RECEIVE_HOOK" ]; then
    log_info "Creating post-receive hook..."
    cat > "$POST_RECEIVE_HOOK" << 'EOF'
#!/bin/bash
# Post-receive hook: triggered when code is pushed to this repository

while read oldrev newrev refname; do
    branch=$(git rev-parse --symbolic --abbrev-ref $refname)

    if [ "$branch" = "main" ]; then
        echo "=========================================="
        echo "Deploying branch: $branch"
        echo "Git SHA: $newrev"
        echo "=========================================="

        # Trigger build and deploy pipeline
        # Note: This assumes build_and_deploy.sh is in the repo
        if [ -f "./scripts/build_and_deploy.sh" ]; then
            bash ./scripts/build_and_deploy.sh
        else
            echo "Error: build_and_deploy.sh not found"
            exit 1
        fi
    fi
done
EOF
    chmod +x "$POST_RECEIVE_HOOK"
    log_success "Post-receive hook created and made executable"
else
    log_info "Post-receive hook already exists"
fi

# === Configure git settings ===
log_info "Configuring additional git settings..."
git config pull.rebase false  # Use merge for git pull
git config fetch.prune true   # Auto-prune deleted remote branches
log_success "Git settings configured"

# === Display configuration ===
log_info "Git configuration summary:"
echo "  Repository: $REPO_PATH"
echo "  User: $(git config user.name) <$(git config user.email)>"
echo "  Remote: $(git config --get remote.origin.url 2>/dev/null || echo 'Not configured')"
echo "  Hooks: $HOOKS_DIR"
echo "  SSH Key: $SSH_KEY_PATH"

# === Verify git setup ===
log_info "Verifying git setup..."
if git rev-parse --git-dir > /dev/null 2>&1; then
    log_success "Git repository is valid"
else
    log_error "Git repository validation failed"
    exit 1
fi

log_success "Git repository setup completed successfully!"
exit 0
