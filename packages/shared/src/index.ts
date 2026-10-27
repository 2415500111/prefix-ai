// Hand-written until types are generated from the API's OpenAPI schema; keep in
// sync with apps/api/src/prefix_api/schemas/health.py.
export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
}
