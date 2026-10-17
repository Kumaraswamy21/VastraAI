import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import CredentialsProvider from "next-auth/providers/credentials";
import { internalToken } from "@/lib/internal-token";

function backendUrl(path: string): string {
  const base = process.env.BACKEND_API_URL;
  if (!base && process.env.NODE_ENV === "production") {
    throw new Error("BACKEND_API_URL is not configured on the frontend server");
  }
  return new URL(path, base ?? "http://127.0.0.1:8000").toString();
}

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 },
  pages: { signIn: "/sign-in", error: "/sign-in" },
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
    CredentialsProvider({
      name: "Email and password",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials.password) return null;
        const response = await fetch(backendUrl("/auth/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: credentials.email, password: credentials.password }),
          cache: "no-store",
        });
        if (!response.ok) return null;
        const user = await response.json() as { id: string; email: string; auth_version: number };
        return { id: user.id, email: user.email, authVersion: user.auth_version };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account, profile }) {
      if (account?.provider === "google") {
        const googleProfile = profile as { sub?: string; email?: string; email_verified?: boolean } | undefined;
        if (!googleProfile?.sub || !googleProfile.email || googleProfile.email_verified !== true) {
          throw new Error("Google email must be verified");
        }
        const endpoint = backendUrl("/auth/google");
        const authorization = `Bearer ${internalToken("nextauth", { scope: "account:sync" })}`;
        let response: Response;
        try {
          response = await fetch(endpoint, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: authorization,
            },
            body: JSON.stringify({ subject: googleProfile.sub, email: googleProfile.email }),
            cache: "no-store",
          });
        } catch (error) {
          throw new Error("Google account sync could not reach BACKEND_API_URL", { cause: error });
        }
        if (!response.ok) throw new Error(`Google account sync returned HTTP ${response.status}`);
        const identity = await response.json() as { id: string; email: string; auth_version: number };
        token.uid = identity.id;
        token.email = identity.email;
        token.authVersion = identity.auth_version;
      } else if (user) {
        token.uid = user.id;
        token.authVersion = user.authVersion;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user && typeof token.uid === "string") {
        session.user.id = token.uid;
        session.user.authVersion = token.authVersion as number;
      }
      return session;
    },
  },
};
