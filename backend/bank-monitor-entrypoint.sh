#!/bin/sh
set -eu

# Railway volumes mount at runtime and may be owned by root. Create only the
# dedicated profile tree, lock it down, then drop privileges permanently.
profile_root=/data/profiles
mkdir -p "$profile_root"
chown -R bankworker:bankworker "$profile_root"
chmod 0700 "$profile_root"

exec setpriv --reuid=10001 --regid=10001 --init-groups -- "$@"
