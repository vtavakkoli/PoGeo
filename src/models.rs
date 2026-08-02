use rmcp::schemars;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{ai::OllamaClient, config::Config, geo::GeoService};

#[derive(Clone)]
pub struct AppState {
    pub geo: GeoService,
    pub ollama: OllamaClient,
    pub config: Config,
}

#[derive(Debug, Clone, Deserialize, Serialize, schemars::JsonSchema)]
#[serde(rename_all = "camelCase")]
pub struct QueryFeaturesArgs {
    /// Published collection identifier, for example `vienna_places`.
    pub collection: String,
    /// Optional WGS84 bounding box: [minimum longitude, minimum latitude, maximum longitude, maximum latitude].
    pub bbox: Option<Vec<f64>>,
    /// Optional case-insensitive text search over approved descriptive columns.
    pub query: Option<String>,
    /// Maximum number of returned features.
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, Deserialize, Serialize, schemars::JsonSchema)]
#[serde(rename_all = "camelCase")]
pub struct NearbyArgs {
    /// Published point collection identifier.
    pub collection: String,
    /// Longitude in WGS84.
    pub longitude: f64,
    /// Latitude in WGS84.
    pub latitude: f64,
    /// Search radius in metres.
    pub distance_meters: f64,
    /// Maximum number of returned features.
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, Deserialize, Serialize, schemars::JsonSchema)]
#[serde(rename_all = "camelCase")]
pub struct CollectionStatsArgs {
    pub collection: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ItemsQuery {
    pub bbox: Option<String>,
    pub q: Option<String>,
    pub limit: Option<u32>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NearbyQuery {
    pub longitude: f64,
    pub latitude: f64,
    pub distance_meters: f64,
    pub limit: Option<u32>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatRequest {
    pub message: String,
    pub conversation_id: Option<String>,
    pub map_context: Option<MapContext>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MapContext {
    pub bbox: Option<Vec<f64>>,
    pub zoom: Option<f64>,
    pub visible_collections: Option<Vec<String>>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatResponse {
    pub conversation_id: String,
    pub answer: String,
    pub model: String,
    pub tool_calls: Vec<ToolExecutionRecord>,
    pub map: Option<Value>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolExecutionRecord {
    pub name: String,
    pub arguments: Value,
    pub summary: String,
}

#[derive(Debug, Clone)]
pub struct ToolExecution {
    pub content: Value,
    pub map: Option<Value>,
    pub summary: String,
}
