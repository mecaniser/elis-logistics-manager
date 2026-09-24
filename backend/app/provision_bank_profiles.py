"""Create only the worker's private, persistent browser profiles at container start.

This runs as root before the worker permanently drops to UID 10001. It never
copies cookies or credentials from another browser or service.
"""
import os
from pathlib import Path


def provision_profiles(root: Path, tenant_ids: str, uid: int, gid: int, environ=None):
    environ = os.environ if environ is None else environ
    if root.is_symlink() or not root.parent.is_dir() or root.parent.is_symlink():
        raise ValueError('Private profile volume is unavailable.')
    root.mkdir(mode=0o700, exist_ok=True)
    if not root.is_dir():
        raise ValueError('Private profile root is unavailable.')
    os.chown(root, uid, gid)
    root.chmod(0o700)
    ids = [value.strip() for value in tenant_ids.split(',')]
    if not ids or any(not value.isascii() or not value.isdecimal() or int(value) <= 0 or str(int(value)) != value for value in ids):
        raise ValueError('BANK_MONITOR_TENANT_IDS must contain positive numeric IDs.')
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate bank monitor tenant ID.')
    for tenant_id in ids:
        profile = root / tenant_id
        if environ.get(f'BANK_MONITOR_PROFILE_{tenant_id}') != str(profile):
            raise ValueError(f'Worker profile path for tenant {tenant_id} must be {profile}.')
        if profile.is_symlink():
            raise ValueError('Private profile cannot be a symlink.')
        profile.mkdir(mode=0o700, exist_ok=True)
        if not profile.is_dir():
            raise ValueError('Private profile is unavailable.')
        os.chown(profile, uid, gid)
        profile.chmod(0o700)


if __name__ == '__main__':
    provision_profiles(Path('/data/profiles'), os.getenv('BANK_MONITOR_TENANT_IDS', ''), 10001, 10001)
