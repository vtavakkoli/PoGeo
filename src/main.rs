mod ai;
mod api;
mod catalog;
mod config;
mod error;
mod geo;
mod mcp;
mod models;
mod web;

use std::time::Duration;

use axum::{
    Router,
    http::{HeaderName, StatusCode, header},
};
use config::Config;
use mcp::PoGeoMcp;
use rmcp::transport::streamable_http_server::{
    StreamableHttpServerConfig, StreamableHttpService, session::local::LocalSessionManager,
};
use sqlx::postgres::PgPoolOptions;
use tokio_util::sync::CancellationToken;
use tower_http::{
    compression::CompressionLayer,
    cors::{Any, CorsLayer},
    request_id::{MakeRequestUuid, PropagateRequestIdLayer, SetRequestIdLayer},
    sensitive_headers::SetSensitiveRequestHeadersLayer,
    timeout::TimeoutLayer,
    trace::TraceLayer,
};
use tracing::{info, warn};

use crate::{ai::OllamaClient, geo::GeoService, models::AppState};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    init_tracing();

    let config = Config::from_env()?;
    let pool = PgPoolOptions::new()
        .min_connections(config.database_min_connections)
        .max_connections(config.database_max_connections)
        .acquire_timeout(Duration::from_secs(10))
        .connect(&config.database_url)
        .await?;

    sqlx::query("SELECT 1").execute(&pool).await?;

    let state = AppState {
        geo: GeoService::new(pool),
        ollama: OllamaClient::new(
            config.ollama_url.clone(),
            config.ollama_model.clone(),
            config.ai_max_tool_iterations,
        ),
        config: config.clone(),
    };

    let cancellation_token = CancellationToken::new();
    let mcp_state = state.clone();
    let mcp_service = StreamableHttpService::new(
        move || Ok(PoGeoMcp::new(mcp_state.clone())),
        LocalSessionManager::default().into(),
        StreamableHttpServerConfig::default()
            .with_cancellation_token(cancellation_token.child_token()),
    );

    let request_id_header = HeaderName::from_static("x-request-id");
    let app = Router::new()
        .merge(api::router())
        .merge(web::router())
        .nest_service("/mcp", mcp_service)
        .with_state(state)
        .layer(PropagateRequestIdLayer::new(request_id_header.clone()))
        .layer(SetRequestIdLayer::new(request_id_header, MakeRequestUuid))
        .layer(SetSensitiveRequestHeadersLayer::new(std::iter::once(
            header::AUTHORIZATION,
        )))
        .layer(CompressionLayer::new())
        .layer(TimeoutLayer::with_status_code(
            StatusCode::REQUEST_TIMEOUT,
            Duration::from_secs(config.request_timeout_seconds),
        ))
        .layer(
            CorsLayer::new()
                .allow_origin(Any)
                .allow_headers(Any)
                .allow_methods(Any),
        )
        .layer(TraceLayer::new_for_http());

    let listener = tokio::net::TcpListener::bind(&config.bind_address).await?;
    info!(address = %config.bind_address, "PoGeo is ready");
    info!(demo = "http://localhost:8080/demo", "web application");
    info!(mcp = "http://localhost:8080/mcp", "MCP endpoint");

    let shutdown_token = cancellation_token.clone();
    axum::serve(listener, app)
        .with_graceful_shutdown(async move {
            shutdown_signal().await;
            shutdown_token.cancel();
        })
        .await?;

    Ok(())
}

fn init_tracing() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "pogeo=info,tower_http=info".into()),
        )
        .json()
        .init();
}

async fn shutdown_signal() {
    let ctrl_c = async {
        if let Err(error) = tokio::signal::ctrl_c().await {
            warn!(%error, "failed to install Ctrl+C handler");
        }
    };

    #[cfg(unix)]
    let terminate = async {
        match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            Ok(mut signal) => {
                signal.recv().await;
            }
            Err(error) => warn!(%error, "failed to install SIGTERM handler"),
        }
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        () = ctrl_c => {},
        () = terminate => {},
    }
}
