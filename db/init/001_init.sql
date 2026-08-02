CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS pogeo;

CREATE TABLE IF NOT EXISTS pogeo.places (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    district TEXT NOT NULL,
    geom geometry(Point, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS pogeo.stations (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    mode TEXT NOT NULL,
    line TEXT NOT NULL,
    accessible BOOLEAN NOT NULL DEFAULT TRUE,
    geom geometry(Point, 4326) NOT NULL
);

TRUNCATE TABLE pogeo.places, pogeo.stations RESTART IDENTITY;

INSERT INTO pogeo.places (name, category, description, district, geom) VALUES
    ('Stephansdom', 'landmark', 'Gothic cathedral in the historic centre of Vienna.', 'Innere Stadt', ST_SetSRID(ST_MakePoint(16.3731, 48.2085), 4326)),
    ('Vienna City Hall', 'public building', 'Neo-Gothic city hall and seat of the Mayor of Vienna.', 'Innere Stadt', ST_SetSRID(ST_MakePoint(16.3572, 48.2109), 4326)),
    ('Schönbrunn Palace', 'museum', 'Former imperial summer residence and UNESCO World Heritage site.', 'Hietzing', ST_SetSRID(ST_MakePoint(16.3122, 48.1845), 4326)),
    ('Prater Ferris Wheel', 'attraction', 'Historic giant Ferris wheel in the Vienna Prater.', 'Leopoldstadt', ST_SetSRID(ST_MakePoint(16.3959, 48.2166), 4326)),
    ('Belvedere Palace', 'museum', 'Baroque palace complex housing Austrian art.', 'Landstraße', ST_SetSRID(ST_MakePoint(16.3807, 48.1914), 4326)),
    ('MuseumsQuartier', 'culture', 'Large arts and cultural district near the city centre.', 'Neubau', ST_SetSRID(ST_MakePoint(16.3599, 48.2030), 4326)),
    ('Donaupark', 'park', 'Large public park near the Danube Tower.', 'Donaustadt', ST_SetSRID(ST_MakePoint(16.4095, 48.2416), 4326)),
    ('Augarten', 'park', 'Historic Baroque park with extensive lawns and avenues.', 'Leopoldstadt', ST_SetSRID(ST_MakePoint(16.3738, 48.2256), 4326)),
    ('Naschmarkt', 'market', 'Vienna food market with restaurants and international stalls.', 'Mariahilf', ST_SetSRID(ST_MakePoint(16.3610, 48.1984), 4326)),
    ('Danube Tower', 'attraction', 'Observation tower overlooking Vienna and the Danube.', 'Donaustadt', ST_SetSRID(ST_MakePoint(16.4101, 48.2403), 4326));

INSERT INTO pogeo.stations (name, mode, line, accessible, geom) VALUES
    ('Stephansplatz', 'U-Bahn', 'U1, U3', TRUE, ST_SetSRID(ST_MakePoint(16.3717, 48.2082), 4326)),
    ('Karlsplatz', 'U-Bahn', 'U1, U2, U4', TRUE, ST_SetSRID(ST_MakePoint(16.3697, 48.2003), 4326)),
    ('Schottenring', 'U-Bahn', 'U2, U4', TRUE, ST_SetSRID(ST_MakePoint(16.3710, 48.2172), 4326)),
    ('Praterstern', 'Rail and U-Bahn', 'S-Bahn, U1, U2', TRUE, ST_SetSRID(ST_MakePoint(16.3921, 48.2181), 4326)),
    ('Wien Hauptbahnhof', 'Rail and U-Bahn', 'Rail, S-Bahn, U1', TRUE, ST_SetSRID(ST_MakePoint(16.3757, 48.1851), 4326)),
    ('Westbahnhof', 'Rail and U-Bahn', 'Rail, U3, U6', TRUE, ST_SetSRID(ST_MakePoint(16.3382, 48.1967), 4326)),
    ('Floridsdorf', 'Rail and U-Bahn', 'S-Bahn, U6', TRUE, ST_SetSRID(ST_MakePoint(16.4007, 48.2560), 4326)),
    ('Schönbrunn', 'U-Bahn', 'U4', TRUE, ST_SetSRID(ST_MakePoint(16.3190, 48.1867), 4326)),
    ('Museumsquartier', 'U-Bahn', 'U2', TRUE, ST_SetSRID(ST_MakePoint(16.3610, 48.2024), 4326)),
    ('Donauinsel', 'U-Bahn', 'U1', TRUE, ST_SetSRID(ST_MakePoint(16.4096, 48.2283), 4326));

CREATE INDEX IF NOT EXISTS places_geom_gix ON pogeo.places USING GIST (geom);
CREATE INDEX IF NOT EXISTS stations_geom_gix ON pogeo.stations USING GIST (geom);
CREATE INDEX IF NOT EXISTS places_search_idx ON pogeo.places USING GIN (to_tsvector('simple', name || ' ' || category || ' ' || description || ' ' || district));
CREATE INDEX IF NOT EXISTS stations_search_idx ON pogeo.stations USING GIN (to_tsvector('simple', name || ' ' || mode || ' ' || line));

ANALYZE pogeo.places;
ANALYZE pogeo.stations;
