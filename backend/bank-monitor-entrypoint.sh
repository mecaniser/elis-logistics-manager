#!/bin/sh
set -eu

# Railway mounts the persistent volume at runtime. Provision only explicitly
# configured private profiles, then permanently drop privileges.
if [ "${BANK_MONITOR_WORKER_ENABLED:-false}" = true ]; then
  python -m app.provision_bank_profiles
fi

exec setpriv --reuid=10001 --regid=10001 --init-groups -- "$@"
