export type HealthPayload = {
  status: string;
  backend: string;
  database: string;
};

export function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export async function fetchHealth(): Promise<HealthPayload> {
  const response = await fetch(`${apiBase()}/health`);
  if (!response.ok) {
    throw new Error(`Health request failed: ${response.status}`);
  }
  return response.json();
}

export function isHealthy(value: string | undefined): boolean {
  return value === "ok";
}
