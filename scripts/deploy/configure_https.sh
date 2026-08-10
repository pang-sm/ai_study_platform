#!/usr/bin/env bash
set -euo pipefail

# Provision and activate the public-IP Let's Encrypt certificate without
# exposing a private key in logs. The caller must run this script as a user
# with passwordless sudo, as the existing deployment workflow does.

PUBLIC_IP="${AI_STUDY_PUBLIC_IP:-101.32.190.42}"
WEB_ROOT="${AI_STUDY_WEB_ROOT:-/var/www/ai_study_platform}"
REPO_ROOT="${AI_STUDY_REPO_ROOT:-$PWD}"
NGINX_SITE_NAME="${AI_STUDY_NGINX_SITE_NAME:-ai-study-platform.conf}"
NGINX_SITE="/etc/nginx/sites-available/$NGINX_SITE_NAME"
NGINX_LINK="/etc/nginx/sites-enabled/$NGINX_SITE_NAME"
BACKUP_ROOT="${AI_STUDY_BACKUP_ROOT:-/var/backups/ai-study-platform}/https-$(date +%Y%m%d_%H%M%S)"
CERTBOT_VENV="${AI_STUDY_CERTBOT_VENV:-/opt/ai-study-platform-certbot}"
STAGING_CERT_NAME="${AI_STUDY_STAGING_CERT_NAME:-ai-study-platform-staging}"
PRODUCTION_CERT_NAME="${AI_STUDY_PRODUCTION_CERT_NAME:-$PUBLIC_IP}"
STAGING_MARKER="/etc/letsencrypt/.ai-study-platform-staging-verified"
PRODUCTION_LIVE_DIR="/etc/letsencrypt/live/$PRODUCTION_CERT_NAME"
STAGING_LIVE_DIR="/etc/letsencrypt/live/$STAGING_CERT_NAME"
TIMER_NAME="ai-study-platform-certbot-renew"

log() { printf '[https] %s\n' "$*" >&2; }
die() { printf '[https] ERROR: %s\n' "$*" >&2; exit 1; }

version_at_least() {
    python3 - "$1" <<'PY'
import re
import sys

def parse(value):
    return tuple(int(part) for part in re.findall(r"\d+", value)[:3])

sys.exit(0 if parse(sys.argv[1]) >= (5, 4, 0) else 1)
PY
}

certbot_version() {
    "$1" --version 2>&1 | awk '{print $2}'
}

select_certbot() {
    local candidate version
    candidate="$(command -v certbot || true)"
    if [ -n "$candidate" ]; then
        version="$(certbot_version "$candidate")"
        if version_at_least "$version"; then
            printf '%s\n' "$candidate"
            return
        fi
        log "existing Certbot $version is below 5.4; installing an isolated current Certbot"
    fi

    if ! python3 -m venv --help >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y python3-venv
    fi
    if [ ! -x "$CERTBOT_VENV/bin/certbot" ]; then
        sudo python3 -m venv "$CERTBOT_VENV"
        # Keep installer output out of the command substitution that captures
        # the selected executable path.
        sudo "$CERTBOT_VENV/bin/pip" install --upgrade 'certbot>=5.4,<6' >&2
    fi
    candidate="$CERTBOT_VENV/bin/certbot"
    version="$(certbot_version "$candidate")"
    version_at_least "$version" || die "Certbot $version is below required 5.4"
    printf '%s\n' "$candidate"
}

verify_ip_certificate() {
    local certificate="$1" expected_issuer="$2"
    sudo test -r "$certificate" || die "certificate is not readable: $certificate"
    local details
    details="$(sudo openssl x509 -in "$certificate" -noout -issuer -subject -dates -ext subjectAltName)"
    printf '%s\n' "$details"
    printf '%s\n' "$details" | grep -Eq "IP Address:${PUBLIC_IP//./\\.}" || die "certificate SAN does not contain $PUBLIC_IP"
    if [ "$expected_issuer" = "production" ]; then
        printf '%s\n' "$details" | grep -qi "Let's Encrypt" || die "production certificate issuer is not Let's Encrypt"
    fi
}

certificate_is_fresh() {
    local certificate="$1" expiry expiry_epoch
    [ -r "$certificate" ] || return 1
    expiry="$(sudo openssl x509 -in "$certificate" -noout -enddate | cut -d= -f2- || true)"
    expiry_epoch="$(date -d "$expiry" +%s 2>/dev/null || true)"
    [ -n "$expiry_epoch" ] || return 1
    [ "$expiry_epoch" -gt "$(( $(date +%s) + 172800 ))" ] || return 1
    sudo openssl x509 -in "$certificate" -noout -issuer | grep -qi "Let's Encrypt"
}

backup_existing_config() {
    sudo mkdir -p "$BACKUP_ROOT/systemd" "$BACKUP_ROOT/nginx"
    local candidate active_site=""
    for candidate in /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*; do
        [ -e "$candidate" ] || continue
        if sudo grep -q "root $WEB_ROOT;" "$candidate" 2>/dev/null; then
            active_site="$candidate"
            break
        fi
    done

    if [ -n "$active_site" ]; then
        if [ -L "$active_site" ]; then
            NGINX_SITE="$(readlink -f "$active_site")"
            NGINX_LINK="$active_site"
        else
            NGINX_SITE="$active_site"
            NGINX_LINK="$active_site"
        fi
        sudo cp -aL "$NGINX_SITE" "$BACKUP_ROOT/nginx/active.conf"
        log "backed up active nginx site to $BACKUP_ROOT/nginx/active.conf"
    elif [ -f "$NGINX_SITE" ]; then
        sudo cp -a "$NGINX_SITE" "$BACKUP_ROOT/nginx/target.conf"
    fi

    for candidate in /etc/systemd/system/ai-backend.service /etc/systemd/system/ai-backend.service.d/*.conf; do
        [ -e "$candidate" ] || continue
        sudo cp -a --parents "$candidate" "$BACKUP_ROOT/systemd"
    done
    sudo mkdir -p /var/lib/ai_study_platform
    printf '%s\n' "$BACKUP_ROOT" | sudo tee /var/lib/ai_study_platform/last-https-backup >/dev/null
}

install_nginx_config() {
    local rendered
    rendered="$(mktemp)"
    sed \
        -e "s#__PUBLIC_IP__#$PUBLIC_IP#g" \
        -e "s#__WEB_ROOT__#$WEB_ROOT#g" \
        -e "s#__CERT_ROOT__#$PRODUCTION_LIVE_DIR#g" \
        "$REPO_ROOT/deploy/nginx-ai-study-platform.conf.example" > "$rendered"
    sudo install -o root -g root -m 0644 "$rendered" "$NGINX_SITE"
    rm -f "$rendered"
    if [ "$NGINX_LINK" = "$NGINX_SITE" ]; then
        :
    elif [ -n "$NGINX_LINK" ]; then
        sudo ln -sfn "$NGINX_SITE" "$NGINX_LINK"
    else
        sudo mkdir -p /etc/nginx/sites-enabled
        sudo ln -sfn "$NGINX_SITE" "$NGINX_LINK"
    fi
    if ! sudo nginx -t; then
        die "nginx configuration test failed; previous config remains in $BACKUP_ROOT/nginx"
    fi
    sudo systemctl reload nginx
    log "nginx HTTPS configuration installed and reloaded"
}

install_renewal() {
    local hook service timer nginx_bin systemctl_bin
    nginx_bin="$(command -v nginx)"
    systemctl_bin="$(command -v systemctl)"
    hook="/etc/letsencrypt/renewal-hooks/deploy/ai-study-platform-nginx-reload"
    sudo mkdir -p "$(dirname "$hook")"
    sudo tee "$hook" >/dev/null <<HOOK
#!/usr/bin/env bash
set -euo pipefail
$nginx_bin -t
$systemctl_bin reload nginx
HOOK
    sudo chmod 0755 "$hook"

    service="/etc/systemd/system/$TIMER_NAME.service"
    timer="/etc/systemd/system/$TIMER_NAME.timer"
    sudo tee "$service" >/dev/null <<SERVICE
[Unit]
Description=Renew ai_study_platform Let's Encrypt IP certificate

[Service]
Type=oneshot
ExecStart=$CERTBOT_BIN renew --quiet
SERVICE
    sudo tee "$timer" >/dev/null <<TIMER
[Unit]
Description=Twice-daily ai_study_platform certificate renewal

[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=30m
Persistent=true

[Install]
WantedBy=timers.target
TIMER
    sudo systemctl daemon-reload
    sudo systemctl enable --now "$TIMER_NAME.timer"
    sudo systemctl is-active --quiet "$TIMER_NAME.timer" || die "renewal timer is not active"
    log "renewal timer active: $TIMER_NAME.timer"
}

allow_web_ports_when_ufw_is_active() {
    if ! command -v ufw >/dev/null 2>&1; then
        log "ufw is not installed; leaving cloud firewall unchanged"
        return
    fi
    local ufw_status
    ufw_status="$(sudo ufw status 2>/dev/null | head -n 1 || true)"
    if printf '%s\n' "$ufw_status" | grep -qi "Status: active"; then
        sudo ufw allow 80/tcp comment 'ai-study-platform HTTP/ACME' >/dev/null
        sudo ufw allow 443/tcp comment 'ai-study-platform HTTPS' >/dev/null
        log "UFW active; HTTP and HTTPS rules applied"
    else
        log "UFW is not active; leaving host firewall unchanged"
    fi
}

command -v python3 >/dev/null || die "python3 is required"
command -v openssl >/dev/null || die "openssl is required"
command -v nginx >/dev/null || die "nginx is required"
sudo test -d "$WEB_ROOT" || die "web root does not exist: $WEB_ROOT"

log "nginx version: $(nginx -v 2>&1)"
log "public IP: $PUBLIC_IP"
log "web root: $WEB_ROOT"
backup_existing_config
CERTBOT_BIN="$(select_certbot)"
log "Certbot version: $(certbot_version "$CERTBOT_BIN")"
sudo mkdir -p "$WEB_ROOT/.well-known/acme-challenge"
sudo chmod 0755 "$WEB_ROOT/.well-known" "$WEB_ROOT/.well-known/acme-challenge"

if [ ! -f "$STAGING_MARKER" ]; then
    log "requesting Let's Encrypt staging IP certificate for preflight"
    sudo "$CERTBOT_BIN" certonly --webroot --webroot-path "$WEB_ROOT" \
        --cert-name "$STAGING_CERT_NAME" --ip-address "$PUBLIC_IP" \
        --preferred-profile shortlived \
        --server https://acme-staging-v02.api.letsencrypt.org/directory \
        --non-interactive --agree-tos --register-unsafely-without-email
    verify_ip_certificate "$STAGING_LIVE_DIR/fullchain.pem" staging
    sudo install -o root -g root -m 0644 /dev/null "$STAGING_MARKER"
    sudo "$CERTBOT_BIN" delete --cert-name "$STAGING_CERT_NAME" --non-interactive || true
    log "staging IP certificate verified and removed"
else
    log "staging IP certificate already verified; reusing marker"
fi

if certificate_is_fresh "$PRODUCTION_LIVE_DIR/fullchain.pem"; then
    log "existing production Let's Encrypt certificate is fresh; no replacement requested"
else
    log "requesting production Let's Encrypt IP certificate"
    sudo "$CERTBOT_BIN" certonly --webroot --webroot-path "$WEB_ROOT" \
        --cert-name "$PRODUCTION_CERT_NAME" --ip-address "$PUBLIC_IP" \
        --preferred-profile shortlived \
        --non-interactive --agree-tos --register-unsafely-without-email \
        --keep-until-expiring
fi
verify_ip_certificate "$PRODUCTION_LIVE_DIR/fullchain.pem" production
install_nginx_config
allow_web_ports_when_ufw_is_active
install_renewal

log "HTTPS preflight complete; backup: $BACKUP_ROOT"
log "certificate paths: $PRODUCTION_LIVE_DIR/fullchain.pem and privkey.pem"
