/// Returns the file path passed as the first CLI argument, if any (e.g. `mdview.exe file.md`).
#[tauri::command]
pub fn initial_file_path() -> Option<String> {
    std::env::args().nth(1)
}

/// Called once by the frontend shortly after startup. WebView2 sometimes fails to paint
/// elements laid out away from the initial content flow (e.g. a right-aligned toolbar item)
/// on their first layout; nudging the window size by 1px and back forces a repaint that fixes it.
#[tauri::command]
pub fn finish_startup(app: tauri::AppHandle) -> Result<(), String> {
    use tauri::Manager;

    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "メインウィンドウが見つかりません".to_string())?;

    let size = window.inner_size().map_err(|e| e.to_string())?;
    window
        .set_size(tauri::Size::Physical(tauri::PhysicalSize {
            width: size.width + 1,
            height: size.height,
        }))
        .map_err(|e| e.to_string())?;
    window
        .set_size(tauri::Size::Physical(size))
        .map_err(|e| e.to_string())?;

    Ok(())
}

/// Launches `command path` as a new, unmanaged process (fire-and-forget; mdview does not wait
/// for or track the editor). `command` is always the user-configured editor setting, never
/// arbitrary frontend input, so this does not amount to a general command-execution capability.
#[tauri::command]
pub fn open_in_editor(command: String, path: String) -> Result<(), String> {
    std::process::Command::new(&command)
        .arg(&path)
        .spawn()
        .map(|_child| ())
        .map_err(|e| format!("エディタの起動に失敗しました: {command} ({e})"))
}
