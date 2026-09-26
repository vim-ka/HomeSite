# Shared helper: replace placeholder secrets in an .env file with random ones.
# Usage: source deploy/lib_secrets.sh; ensure_secrets /opt/homesite/.env
ensure_secrets() {
    local env_file="$1"
    local key current
    for key in JWT_SECRET_KEY INTERNAL_API_SECRET; do
        current="$(grep -E "^${key}=" "$env_file" | head -n1 | cut -d= -f2- || true)"
        if [ -z "$current" ] || [[ "$current" == CHANGE-ME* ]]; then
            local secret
            secret="$(openssl rand -hex 32)"
            if grep -qE "^${key}=" "$env_file"; then
                sed -i "s|^${key}=.*|${key}=${secret}|" "$env_file"
            else
                echo "${key}=${secret}" >> "$env_file"
            fi
            echo "Generated new ${key} (was a placeholder)."
            if [ "$key" = "JWT_SECRET_KEY" ]; then
                echo "  -> all users will have to log in again."
            fi
        fi
    done
    chmod 600 "$env_file"
}
