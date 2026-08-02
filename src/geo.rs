use serde_json::{Value, json};
use sqlx::PgPool;

use crate::{
    catalog::{COLLECTIONS, CollectionDefinition, find_collection},
    error::AppError,
    models::{CollectionStatsArgs, NearbyArgs, QueryFeaturesArgs, ToolExecution},
};

#[derive(Clone)]
pub struct GeoService {
    pool: PgPool,
}

impl GeoService {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub async fn health(&self) -> Result<(), AppError> {
        sqlx::query("SELECT 1").execute(&self.pool).await?;
        Ok(())
    }

    pub fn catalog(&self) -> Value {
        json!({
            "collections": COLLECTIONS,
            "links": [
                {"rel": "self", "type": "application/json", "href": "/collections"},
                {"rel": "service-desc", "type": "application/vnd.oai.openapi+json;version=3.1", "href": "/openapi.json"}
            ]
        })
    }

    pub fn collection(&self, id: &str) -> Result<Value, AppError> {
        let collection = allowed_collection(id)?;
        Ok(json!({
            "id": collection.id,
            "title": collection.title,
            "description": collection.description,
            "itemType": collection.item_type,
            "extent": {"spatial": {"bbox": [[16.18, 48.10, 16.58, 48.33]], "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
            "geometryType": collection.geometry_type,
            "srid": collection.srid,
            "properties": collection.properties,
            "links": [
                {"rel": "items", "type": "application/geo+json", "href": format!("/collections/{}/items", collection.id)},
                {"rel": "statistics", "type": "application/json", "href": format!("/collections/{}/statistics", collection.id)}
            ]
        }))
    }

    pub async fn query_features(
        &self,
        args: &QueryFeaturesArgs,
        maximum_limit: u32,
    ) -> Result<Value, AppError> {
        let collection = allowed_collection(&args.collection)?;
        let bbox = validate_bbox(args.bbox.as_deref())?;
        let limit = clamp_limit(args.limit, maximum_limit);
        let search_expression = collection
            .search_columns
            .iter()
            .map(|column| format!("COALESCE({column}::text, '')"))
            .collect::<Vec<_>>()
            .join(", ");

        let sql = format!(
            r#"
            SELECT jsonb_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(jsonb_agg(feature), '[]'::jsonb),
                'numberReturned', COUNT(*)
            )
            FROM (
                SELECT jsonb_build_object(
                    'type', 'Feature',
                    'id', id,
                    'geometry', ST_AsGeoJSON(geom)::jsonb,
                    'properties', to_jsonb(source_row) - 'id' - 'geom'
                ) AS feature
                FROM (
                    SELECT *
                    FROM {table}
                    WHERE (
                        $1::double precision IS NULL
                        OR ST_Intersects(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
                    )
                    AND (
                        $5::text IS NULL
                        OR concat_ws(' ', {search_expression}) ILIKE '%' || $5 || '%'
                    )
                    ORDER BY id
                    LIMIT $6
                ) AS source_row
            ) AS features
            "#,
            table = collection.table,
        );

        let values = bbox.unwrap_or([f64::NAN; 4]);
        let has_bbox = bbox.is_some();
        let result = sqlx::query_scalar::<_, Value>(&sql)
            .bind(has_bbox.then_some(values[0]))
            .bind(has_bbox.then_some(values[1]))
            .bind(has_bbox.then_some(values[2]))
            .bind(has_bbox.then_some(values[3]))
            .bind(
                args.query
                    .as_deref()
                    .filter(|query| !query.trim().is_empty()),
            )
            .bind(i64::from(limit))
            .fetch_one(&self.pool)
            .await?;

        Ok(result)
    }

    pub async fn feature_by_id(&self, collection_id: &str, id: i64) -> Result<Value, AppError> {
        let collection = allowed_collection(collection_id)?;
        let sql = format!(
            r#"
            SELECT jsonb_build_object(
                'type', 'Feature',
                'id', id,
                'geometry', ST_AsGeoJSON(geom)::jsonb,
                'properties', to_jsonb(source_row) - 'id' - 'geom'
            )
            FROM (SELECT * FROM {} WHERE id = $1) AS source_row
            "#,
            collection.table
        );

        sqlx::query_scalar::<_, Value>(&sql)
            .bind(id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or_else(|| {
                AppError::NotFound(format!(
                    "feature {id} was not found in collection {collection_id}"
                ))
            })
    }

    pub async fn nearby(&self, args: &NearbyArgs, maximum_limit: u32) -> Result<Value, AppError> {
        let collection = allowed_collection(&args.collection)?;
        validate_coordinate(args.longitude, args.latitude)?;
        if !(1.0..=100_000.0).contains(&args.distance_meters) {
            return Err(AppError::BadRequest(
                "distanceMeters must be between 1 and 100000".to_owned(),
            ));
        }
        let limit = clamp_limit(args.limit, maximum_limit);
        let sql = format!(
            r#"
            WITH ranked AS (
                SELECT *, ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                ) AS distance_meters
                FROM {table}
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                    $3
                )
                ORDER BY distance_meters
                LIMIT $4
            )
            SELECT jsonb_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(jsonb_agg(jsonb_build_object(
                    'type', 'Feature',
                    'id', id,
                    'geometry', ST_AsGeoJSON(geom)::jsonb,
                    'properties', (to_jsonb(ranked) - 'id' - 'geom')
                )), '[]'::jsonb),
                'numberReturned', COUNT(*)
            )
            FROM ranked
            "#,
            table = collection.table,
        );

        let result = sqlx::query_scalar::<_, Value>(&sql)
            .bind(args.longitude)
            .bind(args.latitude)
            .bind(args.distance_meters)
            .bind(i64::from(limit))
            .fetch_one(&self.pool)
            .await?;

        Ok(result)
    }

    pub async fn statistics(&self, args: &CollectionStatsArgs) -> Result<Value, AppError> {
        let collection = allowed_collection(&args.collection)?;
        let sql = format!(
            r#"
            SELECT jsonb_build_object(
                'collection', $1::text,
                'featureCount', COUNT(*),
                'extent', CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE ST_AsGeoJSON(ST_Envelope(ST_Extent(geom)))::jsonb
                END
            )
            FROM {}
            "#,
            collection.table
        );

        Ok(sqlx::query_scalar::<_, Value>(&sql)
            .bind(collection.id)
            .fetch_one(&self.pool)
            .await?)
    }

    pub async fn execute_tool(
        &self,
        name: &str,
        arguments: Value,
        maximum_limit: u32,
    ) -> Result<ToolExecution, AppError> {
        match name {
            "list_collections" => Ok(ToolExecution {
                content: self.catalog(),
                map: None,
                summary: format!("Listed {} published collections", COLLECTIONS.len()),
            }),
            "query_features" => {
                let args: QueryFeaturesArgs =
                    serde_json::from_value(arguments).map_err(|error| {
                        AppError::BadRequest(format!("invalid query_features arguments: {error}"))
                    })?;
                let content = self.query_features(&args, maximum_limit).await?;
                let count = feature_count(&content);
                Ok(ToolExecution {
                    map: Some(content.clone()),
                    content,
                    summary: format!("Returned {count} features from {}", args.collection),
                })
            }
            "find_nearby" => {
                let args: NearbyArgs = serde_json::from_value(arguments).map_err(|error| {
                    AppError::BadRequest(format!("invalid find_nearby arguments: {error}"))
                })?;
                let content = self.nearby(&args, maximum_limit).await?;
                let count = feature_count(&content);
                Ok(ToolExecution {
                    map: Some(content.clone()),
                    content,
                    summary: format!(
                        "Found {count} features within {:.0} metres",
                        args.distance_meters
                    ),
                })
            }
            "collection_statistics" => {
                let args: CollectionStatsArgs =
                    serde_json::from_value(arguments).map_err(|error| {
                        AppError::BadRequest(format!(
                            "invalid collection_statistics arguments: {error}"
                        ))
                    })?;
                let content = self.statistics(&args).await?;
                Ok(ToolExecution {
                    content,
                    map: None,
                    summary: format!("Calculated statistics for {}", args.collection),
                })
            }
            _ => Err(AppError::BadRequest(format!("unknown tool: {name}"))),
        }
    }
}

pub fn parse_bbox(value: Option<&str>) -> Result<Option<Vec<f64>>, AppError> {
    value
        .map(|bbox| {
            bbox.split(',')
                .map(|part| {
                    part.trim().parse::<f64>().map_err(|_| {
                        AppError::BadRequest(
                            "bbox must contain four comma-separated numbers".to_owned(),
                        )
                    })
                })
                .collect::<Result<Vec<_>, _>>()
        })
        .transpose()
}

fn allowed_collection(id: &str) -> Result<&'static CollectionDefinition, AppError> {
    find_collection(id)
        .ok_or_else(|| AppError::NotFound(format!("collection {id} is not published")))
}

fn validate_bbox(bbox: Option<&[f64]>) -> Result<Option<[f64; 4]>, AppError> {
    let Some(values) = bbox else {
        return Ok(None);
    };
    let values: [f64; 4] = values.try_into().map_err(|_| {
        AppError::BadRequest("bbox must contain exactly four coordinates".to_owned())
    })?;
    if values.iter().any(|value| !value.is_finite()) {
        return Err(AppError::BadRequest(
            "bbox coordinates must be finite".to_owned(),
        ));
    }
    if values[0] >= values[2] || values[1] >= values[3] {
        return Err(AppError::BadRequest(
            "bbox minimum coordinates must be smaller than maximum coordinates".to_owned(),
        ));
    }
    validate_coordinate(values[0], values[1])?;
    validate_coordinate(values[2], values[3])?;
    Ok(Some(values))
}

fn validate_coordinate(longitude: f64, latitude: f64) -> Result<(), AppError> {
    if !longitude.is_finite()
        || !latitude.is_finite()
        || !(-180.0..=180.0).contains(&longitude)
        || !(-90.0..=90.0).contains(&latitude)
    {
        return Err(AppError::BadRequest(
            "longitude must be between -180 and 180 and latitude between -90 and 90".to_owned(),
        ));
    }
    Ok(())
}

fn clamp_limit(requested: Option<u32>, maximum: u32) -> u32 {
    requested.unwrap_or(100).clamp(1, maximum.max(1))
}

fn feature_count(feature_collection: &Value) -> u64 {
    feature_collection
        .get("numberReturned")
        .and_then(Value::as_u64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::{clamp_limit, parse_bbox, validate_bbox};

    #[test]
    fn parses_valid_bbox() {
        assert_eq!(
            parse_bbox(Some("16.2,48.1,16.6,48.4")).expect("valid bbox"),
            Some(vec![16.2, 48.1, 16.6, 48.4])
        );
    }

    #[test]
    fn rejects_reversed_bbox() {
        assert!(validate_bbox(Some(&[16.6, 48.1, 16.2, 48.4])).is_err());
    }

    #[test]
    fn limit_is_bounded() {
        assert_eq!(clamp_limit(Some(10_000), 500), 500);
        assert_eq!(clamp_limit(Some(0), 500), 1);
        assert_eq!(clamp_limit(None, 500), 100);
    }
}
