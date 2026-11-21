use notify::{Event, RecommendedWatcher, RecursiveMode, Watcher};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};

/// Holds one watcher per currently-open tab, keyed by the watched file's path. Each open tab
/// gets its own entry so file changes are detected regardless of which tab is active; starting
/// a new watch for a path that's already watched replaces (and thus drops/unregisters) the
/// previous watcher for that path.
#[derive(Default)]
pub struct WatcherState(pub Mutex<HashMap<String, RecommendedWatcher>>);

#[tauri::command]
pub fn start_watching(app: AppHandle, state: State<WatcherState>, path: String) -> Result<(), String> {
    let target = PathBuf::from(&path);
    let parent = target
        .parent()
        .ok_or_else(|| format!("ファイルの親ディレクトリを特定できません: {path}"))?
        .to_path_buf();

    let emitted_path = path.clone();
    let mut watcher = notify::recommended_watcher(move |res: notify::Result<Event>| {
        let Ok(event) = res else { return };
        if event.paths.iter().any(|p| *p == target) {
            let _ = app.emit("file-changed", emitted_path.clone());
        }
    })
    .map_err(|e| e.to_string())?;

    watcher
        .watch(&parent, RecursiveMode::NonRecursive)
        .map_err(|e| e.to_string())?;

    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    guard.insert(path, watcher);
    Ok(())
}

/// Stops watching a tab's file (called when its tab is closed). Dropping the removed
/// `RecommendedWatcher` unregisters it; a path with no active watcher is a no-op.
#[tauri::command]
pub fn stop_watching(state: State<WatcherState>, path: String) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    guard.remove(&path);
    Ok(())
}
