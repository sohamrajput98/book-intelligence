/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "books.toscrape.com" },
      { protocol: "http", hostname: "books.toscrape.com" }
    ]
  }
};

export default nextConfig;
