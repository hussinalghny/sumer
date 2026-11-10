/** @type {import('next').NextConfig} */
const API = process.env.SUMER_MAIL_API_INTERNAL || "http://127.0.0.1:8100";

// سياسة صارمة. الصور الخارجية مسموحة تقنياً فقط لأن المستخدم يختار «عرض الصور» لرسالة معينة،
// والمعقِّم بالخادم يحذفها افتراضياً. لا سكربتات أو خطوط من أي طرف ثالث.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'" + (process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""),
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self'",
  "connect-src 'self'",
  "frame-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Content-Security-Policy", value: csp },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "interest-cohort=(), browsing-topics=(), geolocation=(), camera=(), microphone=()" },
      ],
    }];
  },
};
export default nextConfig;
