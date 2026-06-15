use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

/// 弹出目录选择器，返回用户选中的文件夹绝对路径（取消则 None）。
///
/// 扫描、读 EXIF、复制副本、归档等文件操作都已下沉到 sidecar（Python）；Rust 壳只负责
/// 需要原生 GUI 的能力——目录选择对话框。命令声明为 async，Tauri 会在非主线程上执行，
/// blocking_pick_folder 才不会和主线程 UI 死锁。
#[tauri::command]
async fn pick_folder(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let Some(picked) = app.dialog().file().blocking_pick_folder() else {
        return Ok(None); // 用户取消
    };
    let dir = picked.into_path().map_err(|e| e.to_string())?;
    Ok(Some(dir.to_string_lossy().into_owned()))
}

/// 用系统默认方式打开一个路径（完成阶段用于打开输出目录）。
#[tauri::command]
fn open_path(app: tauri::AppHandle, path: String) -> Result<(), String> {
    app.opener()
        .open_path(path, None::<&str>)
        .map_err(|e| e.to_string())
}

/// 退出应用——用户在首次下载确认弹窗点「不同意」时调用。
#[tauri::command]
fn exit_app(app: tauri::AppHandle) {
    app.exit(0);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![pick_folder, open_path, exit_app])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
