; Keeper —— Windows 安装/卸载钩子（NSIS）
;
; 用途：卸载时「可选地」清理 Keeper 在用户目录下的数据。这些数据不在安装目录里，
;       系统默认卸载器删不到，不清理会残留（尤其模型权重可能占数 GB）。
;
; 接线：tauri.conf.json5 的 bundle.windows.nsis.installerHooks 指向本文件。
; 约定：Tauri 的 NSIS 模板会【无条件插入】下面四个宏，故四个都必须定义；
;       用不到的留空，否则 makensis 会报「宏未定义」而打包失败。
;
; 数据位置（bundle id = ai.mintpop.keeper）：
;   KEEPER_HOME       = %APPDATA%\ai.mintpop.keeper            （Roaming：workspace 项目副本 / keeper.db / *_key）
;   KEEPER_MODELS_DIR = %LOCALAPPDATA%\ai.mintpop.keeper\models （Local：本地模型权重，可能数 GB）
;   WebView2 数据     = %LOCALAPPDATA%\ai.mintpop.keeper\EBWebView
;   —— 三者都在 \ai.mintpop.keeper 下，故整删 Roaming + Local 这两个根目录即可一次清净。
;
; 备注：若日后想改成复用 Tauri 自带的「Delete application data」复选框来决定是否清理，
;       可把下面的弹窗逻辑替换为对模板复选框状态变量的判断（需以你当前 Tauri 版本的
;       NSIS 模板为准核对变量名，避免引用未定义变量导致打包失败）。当前实现自带询问，
;       不依赖模板内部变量，最稳。

!macro NSIS_HOOK_PREINSTALL
!macroend

!macro NSIS_HOOK_POSTINSTALL
!macroend

!macro NSIS_HOOK_PREUNINSTALL
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ; 静默卸载（/S，如企业批量/自动化）不弹窗、不删数据：无人值守场景保守为先，
  ; 绝不在用户不知情时删掉其照片项目副本。
  IfSilent keeper_skip_cleanup
    MessageBox MB_YESNO|MB_ICONQUESTION \
      "是否同时删除 Keeper 的本地数据？$\r$\n$\r$\n将清除：项目副本(workspace)、数据库、本地模型缓存（可能占用数 GB）。$\r$\n若打算重装并保留这些数据，请选「否」。" \
      IDNO keeper_skip_cleanup
      ; 用户确认删除：两个数据根整删（Roaming + Local，含 WebView2 数据）
      RMDir /r "$APPDATA\ai.mintpop.keeper"
      RMDir /r "$LOCALAPPDATA\ai.mintpop.keeper"
  keeper_skip_cleanup:
!macroend
