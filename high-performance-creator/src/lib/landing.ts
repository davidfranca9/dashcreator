import type { CSSProperties } from "react";

export const CTA_LABEL = "Quero mudar meu jogo antes da Black Friday";

// Atraso de entrada: --reveal-delay para blocos que aparecem ao rolar, --d para o topo da página.
export const revealDelay = (ms: number) => ({ "--reveal-delay": `${ms}ms` }) as CSSProperties;
export const heroDelay = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;
