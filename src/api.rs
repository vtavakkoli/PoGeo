use axum::{
    Json, Router,
    extract::{Path, Query, State},
    routing::{get, post},
};
use serde_json::{Value, json};

use crate::{
    error::AppError,
    geo::parse_bbox,
    models::{
        AppState, ChatRequest, ChatResponse, CollectionStatsArgs, ItemsQuery, NearbyArgs,
        NearbyQuery, QueryFeaturesArgs,
    },
};

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", get(root))
        .route("/health", get(health))
        .route("/api", get(api_definition))
        .route("/conformance", get(conformance))
        .route("/openapi.json", get(openapi))
        .route("/collections", get(collections))
        .route("/collections/{collection_id}", get(collection))
        .route(
            "/collections/{collection_id}/items",
            get(collection_items),
        )
        .route(
            "/collections/{collection_id}/items/{feature_id}",
            get(collection_item),
        )
        .route(
            "/collections/{collection_id}/nearby",
            get(collection_nearby),
        )
        .route(
            "/collections/{collection_id}/statistics",
            get(collection_statistics),
        )
        .route("/api/chat", post(chat))
}

async fn root() -> Json<Value> {
    Json(json!({
        "title": "PoGeo",
        "description": "AI-native, MCP-ready geospatial API server for PostGIS",
        "version": env!("CARGO_PKG_VERSION"),
        "links": [
            {"rel": "service-desc", "type": "application/vnd.oai.openapi+json;version=3.1", "href": "/openapi.json"},
            {"rel": "data", "type": "application/json", "href": "/collections"},
            {"rel": "mcp", "type": "application/json", "href": "/mcp"},
            {"rel": "demo", "type": "text/html", "href": "/demo"}
        ]
    }))
}

async fn health(State(state): State<AppState>) -> Result<Json<Value>, AppError> {
    state.geo.health().await?;
    Ok(Json(json!({
        "status": "ok",
        "database": "connected",
        "aiModel": state.ollama.model(),
        "version": env!("CARGO_PKG_VERSION")
    })))
}

async fn api_definition() -> Json<Value> {
    Json(json!({
        "title": "PoGeo API",
        "description": "PostGIS data through OGC-style JSON APIs, MCP tools, and Ollama chat.",
        "endpoints": {
            "collections": "/collections",
            "openapi": "/openapi.json",
            "mcp": "/mcp",
            "chat": "/api/chat",
            "demo": "/demo"
        }
    }))
}

async fn conformance() -> Json<Value> {
    Json(json!({
        "conformsTo": [
            "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson"
        ],
        "note": "PoGeo v0.1 exposes an OGC API Features-compatible subset; formal conformance testing is planned."
    }))
}

async fn collections(State(state): State<AppState>) -> Json<Value> {
    Json(state.geo.catalog())
}

async fn collection(
    State(state): State<AppState>,
    Path(collection_id): Path<String>,
) -> Result<Json<Value>, AppError> {
    Ok(Json(state.geo.collection(&collection_id)?))
}

async fn collection_items(
    State(state): State<AppState>,
    Path(collection_id): Path<String>,
    Query(query): Query<ItemsQuery>,
) -> Result<Json<Value>, AppError> {
    let args = QueryFeaturesArgs {
        collection: collection_id,
        bbox: parse_bbox(query.bbox.as_deref())?,
        query: query.q,
        limit: query.limit,
    };
    Ok(Json(
        state
            .geo
            .query_features(&args, state.config.max_features)
            .await?,
    ))
}

async fn collection_item(
    State(state): State<AppState>,
    Path((collection_id, feature_id)): Path<(String, i64)>,
) -> Result<Json<Value>, AppError> {
    Ok(Json(
        state.geo.feature_by_id(&collection_id, feature_id).await?,
    ))
}

async fn collection_nearby(
    State(state): State<AppState>,
    Path(collection_id): Path<String>,
    Query(query): Query<NearbyQuery>,
) -> Result<Json<Value>, AppError> {
    let args = NearbyArgs {
        collection: collection_id,
        longitude: query.longitude,
        latitude: query.latitude,
        distance_meters: query.distance_meters,
        limit: query.limit,
    };
    Ok(Json(
        state.geo.nearby(&args, state.config.max_features).await?,
    ))
}

async fn collection_statistics(
    State(state): State<AppState>,
    Path(collection_id): Path<String>,
) -> Result<Json<Value>, AppError> {
    Ok(Json(
        state
            .geo
            .statistics(&CollectionStatsArgs {
                collection: collection_id,
            })
            .await?,
    ))
}

async fn chat(
    State(state): State<AppState>,
    Json(request): Json<ChatRequest>,
) -> Result<Json<ChatResponse>, AppError> {
    if request.message.trim().is_empty() {
        return Err(AppError::BadRequest(
            "message must not be empty".to_owned(),
        ));
    }
    Ok(Json(state.ollama.chat(&state, request).await?))
}

async fn openapi() -> Json<Value> {
    Json(json!({
        "openapi": "3.1.0",
        "info": {
            "title": "PoGeo API",
            "version": env!("CARGO_PKG_VERSION"),
            "description": "Safe PostGIS feature APIs, Ollama chat, and Model Context Protocol tools."
        },
        "servers": [{"url": "/"}],
        "paths": {
            "/health": {"get": {"summary": "Readiness check", "responses": {"200": {"description": "Healthy"}}}},
            "/collections": {"get": {"summary": "List published collections", "responses": {"200": {"description": "Collection catalog"}}}},
            "/collections/{collectionId}/items": {
                "get": {
                    "summary": "Query GeoJSON features",
                    "parameters": [
                        {"name": "collectionId", "in": "path", "required": true, "schema": {"type": "string"}},
                        {"name": "bbox", "in": "query", "schema": {"type": "string"}},
                        {"name": "q", "in": "query", "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 500}}
                    ],
                    "responses": {"200": {"description": "GeoJSON FeatureCollection"}}
                }
            },
            "/api/chat": {
                "post": {
                    "summary": "Ask Ollama a spatial question",
                    "requestBody": {"required": true, "content": {"application/json": {"schema": {"type": "object", "required": ["message"], "properties": {"message": {"type": "string"}}}}}},
                    "responses": {"200": {"description": "AI answer and optional map result"}, "503": {"description": "Ollama unavailable"}}
                }
            },
            "/mcp": {"post": {"summary": "MCP Streamable HTTP endpoint", "responses": {"200": {"description": "MCP response"}}}}
        }
    }))
}

