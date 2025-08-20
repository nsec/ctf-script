use std::process::Command;

fn main() {
    // Tell Cargo that if the given file changes, to rerun this build script.
    println!("cargo::rerun-if-changed=client/src/");
    println!("cargo::rerun-if-changed=client/static/");

    Command::new("npm")
        .current_dir(std::env::var("CARGO_MANIFEST_DIR").unwrap() + "/client")
        .args(&["run", "build"])
        .status()
        .unwrap();
}
