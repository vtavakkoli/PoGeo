use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use tracing::{debug, warn};
use uuid::Uuid;

use crate::{
    error::AppError,
    models::{AppState, ChatRequest, ChatResponse, ToolExecutionRecord},
};

#[derive(Clone)]
pub struct OllamaClient {
    client: Client,
    base_url: String,
    model: String,
    maximum_tool_iterations: usize,
}

impl OllamaClient {
    pub fn new(base_url: String, model: String, maximum_tool_iterations: usize) -> Self {
        Self {
            client: Client::new(),
            base_url: base_url.trim_end_matches('/').to_owned(),
            model,
            maximum_tool_iterations,
        }
    }

    pub fn model(&self) -> &str {
        &self.model
    }

    pub async fn chat(
        &self,
        state: &AppState,
        request: ChatRequest,
    ) -> Result<ChatResponse, AppError> {
        let conversation_id = request
            .conversation_id
            .unwrap_or_else(|| Uuid::new_v4().to_string());
        let mut messages = vec![
            OllamaMessage::text("system", system_prompt(state.config.max_features)),
            OllamaMessage::text("user", user_prompt(&request)),
        ];
        let mut execution_records = Vec::new();
        let mut map = None;

        for iteration in 0..self.maximum_tool_iterations {
            let response = self.complete(&messages).await?;
            let assistant = response.message;
            let calls = assistant.tool_calls.clone().unwrap_or_default();
            messages.push(assistant.clone());

            if calls.is_empty() {
                let answer = if assistant.content.trim().is_empty() {
                    "The model completed without returning a textual answer.".to_owned()
                } else {
                    assistant.content
                };
                return Ok(ChatResponse {
                    conversation_id,
                    answer,
                    model: self.model.clone(),
                    tool_calls: execution_records,
                    map,
                });
            }

            debug!(
                iteration,
                calls = calls.len(),
                "executing Ollama tool calls"
            );
            for call in calls {
                let name = call.function.name;
                let arguments = call.function.arguments;
                let execution = state
                    .geo
                    .execute_tool(&name, arguments.clone(), state.config.max_features)
                    .await?;
                if execution.map.is_some() {
                    map = execution.map.clone();
                }
                execution_records.push(ToolExecutionRecord {
                    name: name.clone(),
                    arguments,
                    summary: execution.summary,
                });
                messages.push(OllamaMessage::tool(
                    name,
                    compact_tool_content(&execution.content),
                ));
            }
        }

        warn!(
            iterations = self.maximum_tool_iterations,
            "Ollama reached the tool iteration limit"
        );
        Ok(ChatResponse {
            conversation_id,
            answer: "I reached the safe tool-execution limit. Refine the question or reduce the requested area."
                .to_owned(),
            model: self.model.clone(),
            tool_calls: execution_records,
            map,
        })
    }

    async fn complete(&self, messages: &[OllamaMessage]) -> Result<OllamaResponse, AppError> {
        let endpoint = format!("{}/api/chat", self.base_url);
        let response = self
            .client
            .post(endpoint)
            .json(&OllamaRequest {
                model: &self.model,
                messages,
                stream: false,
                tools: tool_definitions(),
                options: json!({"temperature": 0.1}),
            })
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AppError::AiUnavailable(format!(
                "Ollama returned {status}: {body}"
            )));
        }

        response
            .json::<OllamaResponse>()
            .await
            .map_err(|error| AppError::InvalidAiResponse(error.to_string()))
    }
}

fn system_prompt(maximum_features: u32) -> String {
    format!(
        "You are PoGeo, a geospatial assistant connected to an allowlisted PostGIS catalog. \
Use tools for every factual spatial answer. Never invent collection names, feature counts, \
coordinates, or query results. Never produce or request raw SQL. Begin with list_collections \
when the available datasets are unclear. Keep results concise and explain which geospatial \
operation was performed. No tool may request more than {maximum_features} features."
    )
}

fn user_prompt(request: &ChatRequest) -> String {
    match &request.map_context {
        Some(context) => format!(
            "User question: {}\nCurrent map context: {}",
            request.message,
            serde_json::to_string(context).unwrap_or_else(|_| "{}".to_owned())
        ),
        None => request.message.clone(),
    }
}

fn compact_tool_content(content: &Value) -> String {
    let mut text = content.to_string();
    const MAX_TOOL_RESULT_CHARS: usize = 80_000;
    if text.len() > MAX_TOOL_RESULT_CHARS {
        text.truncate(MAX_TOOL_RESULT_CHARS);
        text.push_str("… [truncated by PoGeo]");
    }
    text
}

fn tool_definitions() -> Vec<OllamaTool> {
    vec![
        OllamaTool::function(
            "list_collections",
            "List the published and AI-approved geospatial collections.",
            json!({"type": "object", "properties": {}}),
        ),
        OllamaTool::function(
            "query_features",
            "Query an approved collection by bounding box and optional text search.",
            json!({
                "type": "object",
                "required": ["collection"],
                "properties": {
                    "collection": {"type": "string"},
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4
                    },
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500}
                }
            }),
        ),
        OllamaTool::function(
            "find_nearby",
            "Find features within a distance of a WGS84 coordinate, ordered nearest first.",
            json!({
                "type": "object",
                "required": ["collection", "longitude", "latitude", "distanceMeters"],
                "properties": {
                    "collection": {"type": "string"},
                    "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                    "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                    "distanceMeters": {"type": "number", "minimum": 1, "maximum": 100000},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500}
                }
            }),
        ),
        OllamaTool::function(
            "collection_statistics",
            "Return the feature count and spatial extent for an approved collection.",
            json!({
                "type": "object",
                "required": ["collection"],
                "properties": {"collection": {"type": "string"}}
            }),
        ),
    ]
}

#[derive(Debug, Serialize)]
struct OllamaRequest<'a> {
    model: &'a str,
    messages: &'a [OllamaMessage],
    stream: bool,
    tools: Vec<OllamaTool>,
    options: Value,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct OllamaMessage {
    role: String,
    #[serde(default)]
    content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_calls: Option<Vec<OllamaToolCall>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_name: Option<String>,
}

impl OllamaMessage {
    fn text(role: &str, content: String) -> Self {
        Self {
            role: role.to_owned(),
            content,
            tool_calls: None,
            tool_name: None,
        }
    }

    fn tool(name: String, content: String) -> Self {
        Self {
            role: "tool".to_owned(),
            content,
            tool_calls: None,
            tool_name: Some(name),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct OllamaToolCall {
    function: OllamaFunctionCall,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct OllamaFunctionCall {
    name: String,
    arguments: Value,
}

#[derive(Debug, Deserialize)]
struct OllamaResponse {
    message: OllamaMessage,
}

#[derive(Debug, Serialize)]
struct OllamaTool {
    r#type: &'static str,
    function: OllamaFunction,
}

impl OllamaTool {
    fn function(name: &'static str, description: &'static str, parameters: Value) -> Self {
        Self {
            r#type: "function",
            function: OllamaFunction {
                name,
                description,
                parameters,
            },
        }
    }
}

#[derive(Debug, Serialize)]
struct OllamaFunction {
    name: &'static str,
    description: &'static str,
    parameters: Value,
}
