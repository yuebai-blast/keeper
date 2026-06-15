"""下载监控的测试——临时目录模拟文件增长，不依赖网络。"""

import time

from keeper_engine.service.download_monitor import DownloadMonitor, _dir_size


def test_dir_size_sums_all_files(tmp_path):
    (tmp_path / "a").write_bytes(b"xy")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b").write_bytes(b"zzz")
    assert _dir_size(tmp_path) == 5


def test_dir_size_missing_root_is_zero(tmp_path):
    assert _dir_size(tmp_path / "nope") == 0


def test_monitor_tracks_growth(tmp_path):
    mon = DownloadMonitor(tmp_path, interval=0.05)
    mon.start()
    time.sleep(0.12)
    (tmp_path / "weight.bin").write_bytes(b"x" * 2000)
    time.sleep(0.18)
    mon.stop()
    assert mon.downloaded_bytes >= 2000  # 自基线（空目录）起的增量


def test_monitor_stalled_grows_without_writes(tmp_path):
    mon = DownloadMonitor(tmp_path, interval=0.05)
    mon.start()
    time.sleep(0.15)
    mon.stop()
    assert mon.stalled_seconds() > 0  # 无写入 → 停滞时长持续增长
