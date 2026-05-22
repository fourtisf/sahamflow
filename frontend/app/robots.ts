import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: "https://sahamflow.com/sitemap.xml",
    host: "https://sahamflow.com",
  };
}
