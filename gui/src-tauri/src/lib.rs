mod commands;
mod watcher;
mod webview_settings;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .manage(watcher::WatcherState::default())
        .setup(|app| {
            webview_settings::enable_pinch_gestures(app);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::initial_file_path,
            commands::open_in_editor,
            commands::finish_startup,
            watcher::start_watching,
            watcher::stop_watching
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
