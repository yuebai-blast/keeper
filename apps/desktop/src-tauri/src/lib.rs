use tauri_plugin_dialog::DialogExt;

// 支持的图片/RAW 扩展名（与 sidecar imaging.py 保持一致）
const IMAGE_EXTS: &[&str] = &[
    "jpg", "jpeg", "png", "heic", "heif", "webp", "bmp", "tif", "tiff", "cr2", "cr3", "nef",
    "nrw", "arw", "sr2", "srf", "raf", "rw2", "orf", "dng", "pef", "raw",
];

/// 弹出目录选择器，扫描其中的图片/RAW，返回绝对路径列表。
///
/// 文件系统访问只在 Rust 壳里发生（前端碰不到 FS）。命令声明为 async，
/// Tauri 会在非主线程上执行，blocking_pick_folder 才不会和主线程 UI 死锁。
/// 用户取消选择 → 返回空列表。
#[tauri::command]
async fn import_photos(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    let Some(picked) = app.dialog().file().blocking_pick_folder() else {
        return Ok(vec![]); // 用户取消
    };
    let dir = picked.into_path().map_err(|e| e.to_string())?;

    let mut photos = Vec::new();
    for entry in std::fs::read_dir(&dir).map_err(|e| e.to_string())? {
        let path = entry.map_err(|e| e.to_string())?.path();
        if !path.is_file() {
            continue;
        }
        let is_image = path
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| IMAGE_EXTS.contains(&e.to_lowercase().as_str()))
            .unwrap_or(false);
        if is_image {
            photos.push(path.to_string_lossy().into_owned());
        }
    }
    photos.sort();
    Ok(photos)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![import_photos])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
