use std::net::SocketAddr;

use axum::{Json, Router, http::StatusCode, response::IntoResponse, routing::get};

use tower_http::services::ServeDir;

use serde::Serialize;

use clap::Parser;

#[derive(Parser)]
struct Cli {
    #[clap(short, long, default_value = "127.0.0.1:3000")]
    bind_address: SocketAddr,
}

#[tokio::main]
async fn main() {
    // initialize tracing
    tracing_subscriber::fmt::init();

    let cli = Cli::parse();

    // build our application with a route
    let app = Router::new()
        // `GET /` goes to `root`
        .route("/api/hello", get(hello))
        .fallback_service(ServeDir::new("./dist"));

    // run our app with hyper, listening globally on port 3000
    let listener = tokio::net::TcpListener::bind(cli.bind_address)
        .await
        .unwrap();
    axum::serve(listener, app).await.unwrap();
}

// basic handler that responds with a static string
async fn hello() -> impl IntoResponse {
    (
        StatusCode::IM_A_TEAPOT,
        Json(HelloWorld {
            hello: "Hello ".to_string(),
            world: "World!".to_string(),
        }),
    )
}

// the output to our `create_user` handler
#[derive(Serialize)]
struct HelloWorld {
    hello: String,
    world: String,
}
