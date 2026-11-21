use tauri::Manager;

/// Re-enables touchpad/touch pinch gestures in WebView2.
///
/// wry ties `IsPinchZoomEnabled` to `zoomHotkeysEnabled`, so leaving page zoom off (as we do:
/// the app zooms only the Markdown body itself, see spec.md 11.1) also makes WebView2 swallow
/// pinch gestures before the page ever sees them. With pinch enabled again, a touchpad pinch
/// reaches the page as a ctrl+wheel event, which the frontend turns into content zoom and
/// `preventDefault`s so WebView2 never applies its own visual pinch zoom.
pub fn enable_pinch_gestures(app: &tauri::App) {
    #[cfg(windows)]
    for window in app.webview_windows().values() {
        let _ = window.with_webview(|webview| unsafe {
            use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Settings5;
            use windows::core::Interface;

            let settings = webview.controller().CoreWebView2().and_then(|core| core.Settings());
            if let Ok(settings5) = settings.and_then(|s| s.cast::<ICoreWebView2Settings5>()) {
                let _ = settings5.SetIsPinchZoomEnabled(true);
            }
        });
    }
    #[cfg(not(windows))]
    let _ = app;
}
