use notify::{Event, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};

/// Holds the watcher for the currently open file. Starting a new watch replaces
/// (and thus drops/unregisters) any previous one.
#[derive(Default)]
pub struct WatcherState(pub Mutex<Option<RecommendedWatcher>>);

#[tauri::command]
pub fn start_watching(app: AppHandle, state: State<WatcherState>, path: String) -> Result<(), String> {
    let target = PathBuf::from(&path);
    let parent = target
        .parent()
        .ok_or_else(|| format!("ファイルの親ディレクトリを特定できません: {path}"))?
        .to_path_buf();

    let mut watcher = notify::recommended_watcher(move |res: notify::Result<Event>| {
        let Ok(event) = res else { return };
        if event.paths.iter().any(|p| *p == target) {
            let _ = app.emit("file-changed", path.clone());
        }
    })
    .map_err(|e| e.to_string())?;

    watcher
        .watch(&parent, RecursiveMode::NonRecursive)
        .map_err(|e| e.to_string())?;

    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    *guard = Some(watcher);
    Ok(())
}
