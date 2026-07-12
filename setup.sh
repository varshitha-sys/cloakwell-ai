#!/usr/bin/env bash
# Cloakwell DLP proxy — start/stop the mitmproxy addon (proxy/addon.py) that
# intercepts outbound traffic from CLI/agentic AI tools (Claude Code,
# Antigravity, OpenClaw, ...) and runs it through the same classify/redact/
# block pipeline used by the browser extension.
#
# Usage:
#   ./setup.sh [start|stop|status]
#
# 'start' launches the proxy in the background and writes .cloakwell-env.sh
# with the env vars you need to source in whatever shell you'll run the CLI
# tool from (a script can't export vars into your interactive shell for you).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_DIR="$ROOT_DIR/proxy"
MITMDUMP="$PROXY_DIR/.venv/bin/mitmdump"
LISTEN_PORT="${CLOAKWELL_PROXY_PORT:-8443}"
PID_FILE="$ROOT_DIR/.cloakwell-proxy.pid"
LOG_FILE="$ROOT_DIR/cloakwell-proxy.log"
ENV_FILE="$ROOT_DIR/.cloakwell-env.sh"
CA_CERT="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

cmd_status() {
  if is_running; then
    echo "Cloakwell DLP proxy is running (pid $(cat "$PID_FILE"), port $LISTEN_PORT)."
  else
    echo "Cloakwell DLP proxy is not running."
  fi
}

cmd_stop() {
  if is_running; then
    kill "$(cat "$PID_FILE")"
    rm -f "$PID_FILE"
    echo "Stopped Cloakwell DLP proxy."
  else
    echo "Cloakwell DLP proxy is not running."
  fi
  rm -f "$ENV_FILE"
}

cmd_start() {
  if [[ ! -x "$MITMDUMP" ]]; then
    echo "error: $MITMDUMP not found." >&2
    echo "Set up the proxy venv first: cd proxy && uv venv && uv pip install -r requirements.txt" >&2
    exit 1
  fi

  if is_running; then
    echo "Cloakwell DLP proxy already running (pid $(cat "$PID_FILE"))."
  else
    echo "Starting Cloakwell DLP proxy on port $LISTEN_PORT..."
    (cd "$PROXY_DIR" && nohup "$MITMDUMP" -s addon.py --listen-port "$LISTEN_PORT" >"$LOG_FILE" 2>&1 &
     echo $! > "$PID_FILE")

    # First run generates the CA cert; wait for it to show up.
    for _ in $(seq 1 20); do
      [[ -f "$CA_CERT" ]] && break
      sleep 0.5
    done
  fi

  if [[ ! -f "$CA_CERT" ]]; then
    echo "error: CA cert never appeared at $CA_CERT — check $LOG_FILE" >&2
    exit 1
  fi

  cat > "$ENV_FILE" <<EOF
export HTTPS_PROXY=http://localhost:$LISTEN_PORT
export HTTP_PROXY=http://localhost:$LISTEN_PORT
export NODE_EXTRA_CA_CERTS=$CA_CERT
EOF

  cat <<EOF

Cloakwell DLP proxy is up (pid $(cat "$PID_FILE"), log: $LOG_FILE).

Run this in the SAME shell you'll launch your CLI AI tool from
(Claude Code, Antigravity, etc. — anything that respects HTTPS_PROXY):

    source $ENV_FILE
    claude

When you're done, stop the proxy and unset the env vars so you don't
leave traffic routed through a dead proxy:

    ./setup.sh stop
    unset HTTPS_PROXY HTTP_PROXY NODE_EXTRA_CA_CERTS
EOF
}

case "${1:-start}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  *) echo "usage: $0 [start|stop|status]" >&2; exit 1 ;;
esac
