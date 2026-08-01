mod commands;
mod watcher;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .manage(watcher::WatcherState::default())
        .invoke_handler(tauri::generate_handler![
            commands::initial_file_path,
            commands::open_in_editor,
            watcher::start_watching
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
