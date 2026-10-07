import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// base="./" — 백엔드 StaticFiles 가 `/ui/` 에 마운트하고 공개 URL 에는 gateway prefix 가 얹히므로
// 빌드는 prefix 를 몰라야 한다 (snuh-fhir 와 같은 규칙). API 는 `../api/...` 상대 경로.
// dev: 루트(/)에서 서빙 → `../api` 가 `/api` 로 수렴 → 아래 proxy 로 백엔드(:8000)에 넘긴다.
declare const process: { env: Record<string, string | undefined> };
const apiProxy = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: {
      "/api": apiProxy,
    },
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
