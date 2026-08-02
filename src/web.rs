use axum::{
    Router,
    http::{StatusCode, header},
    response::{IntoResponse, Redirect, Response},
    routing::get,
};

use crate::models::AppState;

const INDEX_HTML: &str = include_str!("../web/index.html");
const APP_JS: &str = include_str!("../web/app.js");
const STYLES_CSS: &str = include_str!("../web/styles.css");

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/demo", get(index))
        .route("/demo/", get(index))
        .route("/demo/app.js", get(app_js))
        .route("/demo/styles.css", get(styles_css))
        .route("/docs", get(|| async { Redirect::temporary("/demo") }))
}

async fn index() -> Response {
    asset(INDEX_HTML, "text/html; charset=utf-8")
}

async fn app_js() -> Response {
    asset(APP_JS, "text/javascript; charset=utf-8")
}

async fn styles_css() -> Response {
    asset(STYLES_CSS, "text/css; charset=utf-8")
}

fn asset(content: &'static str, content_type: &'static str) -> Response {
    (
        StatusCode::OK,
        [
            (header::CONTENT_TYPE, content_type),
            (header::CACHE_CONTROL, "public, max-age=300"),
            (header::X_CONTENT_TYPE_OPTIONS, "nosniff"),
        ],
        content,
    )
        .into_response()
}
