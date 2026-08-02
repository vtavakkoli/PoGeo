use std::{env, num::ParseIntError};

use thiserror::Error;

#[derive(Clone, Debug)]
pub struct Config {
    pub bind_address: String,
    pub database_url: String,
    pub database_min_connections: u32,
    pub database_max_connections: u32,
    pub ollama_url: String,
    pub ollama_model: String,
    pub ai_max_tool_iterations: usize,
    pub max_features: u32,
    pub request_timeout_seconds: u64,
}

impl Config {
    pub fn from_env() -> Result<Self, ConfigError> {
        Ok(Self {
            bind_address: env_or("POGEO_BIND_ADDRESS", "0.0.0.0:8080"),
            database_url: env_or(
                "DATABASE_URL",
                "postgres://pogeo:pogeo@localhost:5432/pogeo",
            ),
            database_min_connections: parse_env("POGEO_DB_MIN_CONNECTIONS", 2)?,
            database_max_connections: parse_env("POGEO_DB_MAX_CONNECTIONS", 20)?,
            ollama_url: env_or("OLLAMA_URL", "http://localhost:11434"),
            ollama_model: env_or("OLLAMA_MODEL", "qwen3:4b"),
            ai_max_tool_iterations: parse_env("POGEO_AI_MAX_TOOL_ITERATIONS", 6)?,
            max_features: parse_env("POGEO_MAX_FEATURES", 500)?,
            request_timeout_seconds: parse_env("POGEO_REQUEST_TIMEOUT_SECONDS", 120)?,
        })
    }
}

fn env_or(key: &str, default: &str) -> String {
    env::var(key).unwrap_or_else(|_| default.to_owned())
}

fn parse_env<T>(key: &'static str, default: T) -> Result<T, ConfigError>
where
    T: std::str::FromStr<Err = ParseIntError> + Copy,
{
    match env::var(key) {
        Ok(value) => value
            .parse::<T>()
            .map_err(|source| ConfigError::InvalidInteger { key, source }),
        Err(_) => Ok(default),
    }
}

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("environment variable {key} must be an integer: {source}")]
    InvalidInteger {
        key: &'static str,
        source: ParseIntError,
    },
}
