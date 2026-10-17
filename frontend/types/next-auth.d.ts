import "next-auth";

declare module "next-auth" {
  interface Session {
    user: { id: string; authVersion: number; email?: string | null; name?: string | null; image?: string | null };
  }
  interface User { authVersion?: number }
}
