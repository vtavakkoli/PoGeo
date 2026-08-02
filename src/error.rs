use axum::{
    Json,
    http::StatusCode,
    response::{IntoResponse, Response},
};
use serde_json::json;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("{0}")]
    BadRequest(String),
    #[error("{0}")]
    NotFound(String),
    #[error("database operation failed: {0}")]
    Database(#[from] sqlx::Error),
    #[error("Ollama request failed: {0}")]
    Ollama(#[from] reqwest::Error),
    #[error("AI provider returned an invalid response: {0}")]
    InvalidAiResponse(String),
    #[error("AI provider is unavailable: {0}")]
    AiUnavailable(String),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code) = match &self {
            Self::BadRequest(_) => (StatusCode::BAD_REQUEST, "bad_request"),
            Self::NotFound(_) => (StatusCode::NOT_FOUND, "not_found"),
            Self::Database(_) => (StatusCode::INTERNAL_SERVER_ERROR, "database_error"),
            Self::Ollama(_) | Self::AiUnavailable(_) => {
                (StatusCode::SERVICE_UNAVAILABLE, "ai_unavailable")
            }
            Self::InvalidAiResponse(_) => (StatusCode::BAD_GATEWAY, "invalid_ai_response"),
        };

        let body = Json(json!({
            "error": code,
            "message": self.to_string(),
        }));
        (status, body).into_response()
    }
}
