import { createHmac } from "node:crypto";

type Claims = Record<string, string | number | boolean>;

/** Sign a five-minute identity assertion for the private FastAPI service. */
export function internalToken(subject: string, extra: Claims = {}): string {
  const secret = process.env.AUTH_JWT_SECRET;
  if (!secret || secret.length < 32) throw new Error("AUTH_JWT_SECRET must be at least 32 characters");
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({
    sub: subject,
    iss: "vastraai-web",
    aud: "vastraai-api",
    iat: now,
    exp: now + 300,
    ...extra,
  })).toString("base64url");
  const message = `${header}.${payload}`;
  const signature = createHmac("sha256", secret).update(message).digest("base64url");
  return `${message}.${signature}`;
}
