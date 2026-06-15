"""workspace 文件操作：扫描源文件夹、复制副本、最终归档、清理。

两类复制都走这里：① 导入时把源图复制到 ~/.keeper/workspace/{name}（保护原文件）；
② 完成时把「通过」的副本复制到 ~/Pictures/Keeper/{name}。复制保留元数据（copy2），
目标重名自动避让（沿用桌面端 archive_one 的「name (1).ext」策略）。

只动 workspace 副本与输出目录，绝不写用户源文件夹（照片不出本地、不改原图）。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..util.imaging import ALL_INPUT_EXTS


class WorkspaceService:
    """文件扫描 / 复制 / 删除（纯文件系统操作，无状态）。"""

    @staticmethod
    def scan_images(folder: str) -> list[Path]:
        """列出文件夹内的图片文件（直接子文件，按文件名排序）。目录不存在抛异常。"""
        base = Path(folder)
        if not base.is_dir():
            raise NotADirectoryError(f"不是有效目录：{folder}")
        files = [
            p for p in base.iterdir()
            if p.is_file() and p.suffix.lower() in ALL_INPUT_EXTS
        ]
        return sorted(files, key=lambda p: p.name)

    @staticmethod
    def copy_into(paths: list[str], dest_dir: str) -> list[tuple[str, str]]:
        """把 paths 逐个复制到 dest_dir（重名避让），返回 [(源, 目标)] 映射。

        单张复制失败会抛异常给调用方决定（导入需整体可靠）。
        """
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        mapping: list[tuple[str, str]] = []
        for src in paths:
            target = WorkspaceService._unique_dest(dest, Path(src).name)
            shutil.copy2(src, target)
            mapping.append((src, str(target)))
        return mapping

    @staticmethod
    def remove_dir(path: str) -> None:
        """删除整个目录（best-effort，用于完成后回收 workspace 空间）。"""
        shutil.rmtree(path, ignore_errors=True)

    @staticmethod
    def _unique_dest(dest_dir: Path, filename: str) -> Path:
        """在 dest_dir 下为 filename 找一个不冲突的目标路径（已存在则 name (1).ext…）。"""
        target = dest_dir / filename
        if not target.exists():
            return target
        stem, suffix = target.stem, target.suffix
        i = 1
        while True:
            cand = dest_dir / f"{stem} ({i}){suffix}"
            if not cand.exists():
                return cand
            i += 1
