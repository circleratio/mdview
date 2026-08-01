/// Returns the file path passed as the first CLI argument, if any (e.g. `mdview.exe file.md`).
#[tauri::command]
pub fn initial_file_path() -> Option<String> {
    std::env::args().nth(1)
}
