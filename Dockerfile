# syntax=docker/dockerfile:1.7
FROM rust:1.88-bookworm AS planner
WORKDIR /app
COPY Cargo.toml rust-toolchain.toml ./
COPY src ./src
COPY web ./web
RUN cargo build --release

FROM debian:bookworm-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home pogeo
COPY --from=planner /app/target/release/pogeo /usr/local/bin/pogeo
USER 10001
EXPOSE 8080
ENV POGEO_BIND_ADDRESS=0.0.0.0:8080
ENTRYPOINT ["/usr/local/bin/pogeo"]
