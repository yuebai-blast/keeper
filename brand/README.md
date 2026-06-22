# Keeper（留影）品牌资产

本地优先的 AI 选片工具的标志系统。全部为**矢量（SVG）**，可无损缩放，可直接用于应用图标、UI 内联与文档。

## 设计释义

- **取景框（四角对焦框）**：摄影 / 取景 / 「为每组圈定候选」——对应产品「机器只递候选」的职责边界。
- **K 字母**：被框中、被留下的**那一张**（the keeper）。其开口的 `>` 形同时是一个指向内部的选择卡尺，暗示「这一张，留下」。
- 两个意象融合，克制、可拥有，贴合「照片不出本地、你来做最终裁决」的产品原则。

## 调色板

| 名称 | 用途 | HEX |
| :-- | :-- | :-- |
| 墨黑 Ink | 浅底标志 / 深色界面底 | `#1A1C22` |
| 琥珀 Keeper Gold | 主强调色（被选中的那一张 = 金） | `#E7A23C` |
| 象牙 Ivory | 深底标志 / 文字 | `#F5F2EA` |

## 文件清单

| 文件 | 用途 |
| :-- | :-- |
| `keeper-mark.svg` | 主标志（浅底：墨框 + 琥珀 K） |
| `keeper-mark-dark.svg` | 深底版（象牙框 + 琥珀 K） |
| `keeper-mark-mono.svg` | 单色版，用 `currentColor` 跟随上下文颜色，适合 UI 内联 / 灰度 |
| `keeper-app-icon.svg` | 应用图标（圆角方块，可导出 Tauri 各尺寸 png/icns/ico） |
| `keeper-wordmark.svg` | 横向字标组合（标志 + Keeper + 留影 + 一句话定位） |
| `keeper-brand-board.svg` | 品牌标志板（标志 / 构成 / 图标 / 色彩 / 组合 / 主张） |
| `preview.html` | 浏览器内一览全部资产 |

## 使用约定

- **留白**：标志四周至少保留一个「角标臂长」的安全边距。
- **最小尺寸**：图标 ≥ 24px、字标组合 ≥ 120px 宽，更小请只用纯标志。
- **字体**：字标当前用 `Inter` + `PingFang SC` 占位渲染；**正式交付前请把文字转曲（outline）**，避免缺字体时走样。
- **生成应用图标**：以 `keeper-app-icon.svg` 为母版导出 png，再生成 Tauri 所需的 `icon.icns` / `icon.ico` / 各尺寸 png（放到 `apps/desktop/src-tauri/icons/`）。

## 本地预览

```bash
open brand/preview.html
```
