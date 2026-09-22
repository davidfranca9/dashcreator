// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// Publicação no site do clube (thecreatorsclub.com.br/hpc/): `HPC_BASE=/hpc/ npm run build`
// gera HTML estático já renderizado em .output/public. Sem HPC_BASE, fica igual ao Lovable.
const HPC_BASE = process.env.HPC_BASE;

export default defineConfig(
  HPC_BASE
    ? {
        vite: { base: HPC_BASE },
        nitro: false,
        tanstackStart: {
          server: { entry: "server" },
          router: { basepath: HPC_BASE.replace(/\/$/, "") },
          prerender: { enabled: true, crawlLinks: false, autoSubfolderIndex: true },
          pages: [{ path: "/" }],
        },
      }
    : {
        tanstackStart: {
          // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
          // nitro/vite builds from this
          server: { entry: "server" },
        },
      },
);
