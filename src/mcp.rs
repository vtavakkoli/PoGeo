use rmcp::{
    ErrorData as McpError, RoleServer, ServerHandler,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::*,
    service::RequestContext,
    tool, tool_handler, tool_router,
};
use serde_json::{Value, json};

use crate::{
    models::{AppState, CollectionStatsArgs, NearbyArgs, QueryFeaturesArgs},
};

#[derive(Clone)]
pub struct PoGeoMcp {
    state: AppState,
    tool_router: ToolRouter<Self>,
}

#[tool_router]
impl PoGeoMcp {
    pub fn new(state: AppState) -> Self {
        Self {
            state,
            tool_router: Self::tool_router(),
        }
    }

    #[tool(description = "List the geospatial collections approved for API and AI access")]
    async fn list_collections(&self) -> Result<CallToolResult, McpError> {
        Ok(json_result(self.state.geo.catalog()))
    }

    #[tool(description = "Query an approved PostGIS collection and return a GeoJSON FeatureCollection")]
    async fn query_features(
        &self,
        Parameters(args): Parameters<QueryFeaturesArgs>,
    ) -> Result<CallToolResult, McpError> {
        let value = self
            .state
            .geo
            .query_features(&args, self.state.config.max_features)
            .await
            .map_err(to_mcp_error)?;
        Ok(json_result(value))
    }

    #[tool(description = "Find features near a WGS84 coordinate, ordered by distance")]
    async fn find_nearby(
        &self,
        Parameters(args): Parameters<NearbyArgs>,
    ) -> Result<CallToolResult, McpError> {
        let value = self
            .state
            .geo
            .nearby(&args, self.state.config.max_features)
            .await
            .map_err(to_mcp_error)?;
        Ok(json_result(value))
    }

    #[tool(description = "Get the feature count and spatial extent of an approved collection")]
    async fn collection_statistics(
        &self,
        Parameters(args): Parameters<CollectionStatsArgs>,
    ) -> Result<CallToolResult, McpError> {
        let value = self
            .state
            .geo
            .statistics(&args)
            .await
            .map_err(to_mcp_error)?;
        Ok(json_result(value))
    }
}

#[tool_handler]
impl ServerHandler for PoGeoMcp {
    fn get_info(&self) -> ServerInfo {
        ServerInfo::new(
            ServerCapabilities::builder()
                .enable_tools()
                .enable_resources()
                .build(),
        )
        .with_server_info(Implementation::from_build_env())
        .with_instructions(
            "PoGeo exposes read-only, allowlisted PostGIS discovery and spatial query tools. Raw SQL is intentionally unavailable."
                .to_owned(),
        )
    }

    async fn list_resources(
        &self,
        _request: Option<PaginatedRequestParams>,
        _context: RequestContext<RoleServer>,
    ) -> Result<ListResourcesResult, McpError> {
        Ok(ListResourcesResult {
            resources: vec![
                Resource::new("pogeo://catalog", "PoGeo collection catalog".to_owned()),
                Resource::new("pogeo://conformance", "PoGeo conformance declaration".to_owned()),
            ],
            ..Default::default()
        })
    }

    async fn read_resource(
        &self,
        request: ReadResourceRequestParams,
        _context: RequestContext<RoleServer>,
    ) -> Result<ReadResourceResponse, McpError> {
        let value = match request.uri.as_str() {
            "pogeo://catalog" => self.state.geo.catalog(),
            "pogeo://conformance" => json!({
                "conformsTo": [
                    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
                    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson"
                ]
            }),
            _ => {
                return Err(McpError::resource_not_found(
                    "unknown PoGeo resource",
                    Some(json!({"uri": request.uri})),
                ));
            }
        };

        Ok(ReadResourceResult::new(vec![ResourceContents::text(
            value.to_string(),
            request.uri,
        )])
        .into())
    }
}

fn json_result(value: Value) -> CallToolResult {
    CallToolResult::success(vec![ContentBlock::text(value.to_string())])
}

fn to_mcp_error(error: impl std::fmt::Display) -> McpError {
    McpError::internal_error(error.to_string(), None)
}
