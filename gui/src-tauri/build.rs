fn main() {
    // The window icon (and the exe resource icon) are embedded at compile time, but tauri-build
    // does not watch the icon files, so regenerated icons would not reach the binary until some
    // Rust source changed. Rebuild whenever the icons change.
    println!("cargo:rerun-if-changed=icons");
    tauri_build::build()
}
