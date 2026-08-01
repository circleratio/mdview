/// Returns the file path passed as the first CLI argument, if any (e.g. `mdview.exe file.md`).
#[tauri::command]
pub fn initial_file_path() -> Option<String> {
    std::env::args().nth(1)
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
