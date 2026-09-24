"""Profile provisioning must stay inside the dedicated worker volume."""
import os
import pytest
from app.provision_bank_profiles import provision_profiles


def test_provisions_only_configured_private_profile(tmp_path):
    root = tmp_path / 'profiles'
    provision_profiles(root, '1', os.getuid(), os.getgid(),
                       {'BANK_MONITOR_PROFILE_1': str(root / '1')})
    assert (root / '1').is_dir()
    assert root.stat().st_mode & 0o777 == 0o700
    assert (root / '1').stat().st_mode & 0o777 == 0o700
    assert sorted(path.name for path in root.iterdir()) == ['1']


def test_rejects_symlink_and_mismatched_tenant_path(tmp_path):
    other = tmp_path / 'other'
    other.mkdir()
    root = tmp_path / 'profiles'
    root.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match='volume'):
        provision_profiles(root, '1', os.getuid(), os.getgid(),
                           {'BANK_MONITOR_PROFILE_1': str(root / '1')})
    root.unlink()
    with pytest.raises(ValueError, match='path'):
        provision_profiles(root, '1', os.getuid(), os.getgid(),
                           {'BANK_MONITOR_PROFILE_1': str(root / '2')})
    assert not (root / '1').exists()
