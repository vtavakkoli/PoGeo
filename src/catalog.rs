use serde::Serialize;

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CollectionDefinition {
    pub id: &'static str,
    pub title: &'static str,
    pub description: &'static str,
    pub item_type: &'static str,
    pub geometry_type: &'static str,
    pub srid: i32,
    pub properties: &'static [&'static str],
    #[serde(skip)]
    pub table: &'static str,
    #[serde(skip)]
    pub search_columns: &'static [&'static str],
}

const PLACE_PROPERTIES: &[&str] = &["name", "category", "description", "district"];
const STATION_PROPERTIES: &[&str] = &["name", "mode", "line", "accessible"];

pub const COLLECTIONS: &[CollectionDefinition] = &[
    CollectionDefinition {
        id: "vienna_places",
        title: "Vienna places",
        description: "Demonstration landmarks and public places in Vienna.",
        item_type: "feature",
        geometry_type: "Point",
        srid: 4326,
        properties: PLACE_PROPERTIES,
        table: "pogeo.places",
        search_columns: &["name", "category", "description", "district"],
    },
    CollectionDefinition {
        id: "vienna_stations",
        title: "Vienna mobility stations",
        description: "Demonstration U-Bahn and railway stations in Vienna.",
        item_type: "feature",
        geometry_type: "Point",
        srid: 4326,
        properties: STATION_PROPERTIES,
        table: "pogeo.stations",
        search_columns: &["name", "mode", "line"],
    },
];

pub fn find_collection(id: &str) -> Option<&'static CollectionDefinition> {
    COLLECTIONS.iter().find(|collection| collection.id == id)
}

#[cfg(test)]
mod tests {
    use super::{COLLECTIONS, find_collection};

    #[test]
    fn collection_ids_are_unique() {
        let mut ids = COLLECTIONS
            .iter()
            .map(|collection| collection.id)
            .collect::<Vec<_>>();
        let original_len = ids.len();
        ids.sort_unstable();
        ids.dedup();
        assert_eq!(ids.len(), original_len);
    }

    #[test]
    fn rejects_unknown_collection() {
        assert!(find_collection("private_table").is_none());
    }
}
