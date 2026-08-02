CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS pogeo;

CREATE TABLE IF NOT EXISTS pogeo.places (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    district INTEGER NOT NULL CHECK (district BETWEEN 1 AND 23),
    description TEXT NOT NULL,
    geom geometry(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS places_geom_gix ON pogeo.places USING GIST (geom);
CREATE INDEX IF NOT EXISTS places_category_idx ON pogeo.places (category);
CREATE INDEX IF NOT EXISTS places_district_idx ON pogeo.places (district);

INSERT INTO pogeo.places (name, category, district, description, geom)
VALUES
    ('St. Stephen''s Cathedral', 'landmark', 1, 'Gothic cathedral in Vienna''s historic centre.', ST_SetSRID(ST_MakePoint(16.3731, 48.2085), 4326)),
    ('Hofburg Palace', 'palace', 1, 'Historic imperial palace and museum complex.', ST_SetSRID(ST_MakePoint(16.3656, 48.2064), 4326)),
    ('Albertina', 'museum', 1, 'Art museum near the Vienna State Opera.', ST_SetSRID(ST_MakePoint(16.3682, 48.2045), 4326)),
    ('Belvedere Palace', 'museum', 3, 'Baroque palace complex and art museum.', ST_SetSRID(ST_MakePoint(16.3806, 48.1915), 4326)),
    ('Vienna Central Station', 'transport', 10, 'Vienna''s main railway station.', ST_SetSRID(ST_MakePoint(16.3752, 48.1850), 4326)),
    ('Schönbrunn Palace', 'palace', 13, 'Former imperial summer residence.', ST_SetSRID(ST_MakePoint(16.3122, 48.1845), 4326)),
    ('Schönbrunn Zoo', 'family', 13, 'Historic zoological garden within Schönbrunn.', ST_SetSRID(ST_MakePoint(16.3027, 48.1822), 4326)),
    ('MuseumsQuartier', 'museum', 7, 'Large cultural complex with museums and courtyards.', ST_SetSRID(ST_MakePoint(16.3597, 48.2033), 4326)),
    ('Vienna Prater', 'park', 2, 'Large public park and amusement area.', ST_SetSRID(ST_MakePoint(16.3986, 48.2167), 4326)),
    ('Giant Ferris Wheel', 'family', 2, 'Historic observation wheel in the Prater.', ST_SetSRID(ST_MakePoint(16.3958, 48.2166), 4326)),
    ('Danube Tower', 'landmark', 22, 'Observation tower in Donaupark.', ST_SetSRID(ST_MakePoint(16.4108, 48.2403), 4326)),
    ('Danube Island', 'park', 21, 'Long recreational island in the Danube.', ST_SetSRID(ST_MakePoint(16.3840, 48.2330), 4326)),
    ('Floridsdorf Station', 'transport', 21, 'Major rail and public transport interchange.', ST_SetSRID(ST_MakePoint(16.4009, 48.2564), 4326)),
    ('Vienna City Hall', 'landmark', 1, 'Neo-Gothic seat of the city government.', ST_SetSRID(ST_MakePoint(16.3573, 48.2108), 4326)),
    ('Austrian National Library', 'library', 1, 'National library in the Hofburg complex.', ST_SetSRID(ST_MakePoint(16.3661, 48.2062), 4326))
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    district = EXCLUDED.district,
    description = EXCLUDED.description,
    geom = EXCLUDED.geom;

COMMENT ON TABLE pogeo.places IS 'PoGeo demonstration points of interest in Vienna.';
