// Ajustes rápidos da página: o que ainda depende de um link ou arquivo real.

// Checkout próprio do clube (Mercado Pago), em thecreatorsclub.com.br/checkout/hpc/.
export const CHECKOUT_URL = "https://thecreatorsclub.com.br/checkout/hpc/";

// Vídeo do depoimento. Duas opções:
//  - arquivo em public/, ex.: { src: "/depoimento.mp4", poster: "/depoimento.jpg" }
//  - link de incorporação do YouTube ou Vimeo, ex.: { src: "https://www.youtube.com/embed/ID" }
// Use vertical: true se o vídeo for gravado em pé (9:16). Deixe null para mostrar o espaço reservado.
export const TESTIMONIAL_VIDEO: { src: string; poster?: string; vertical?: boolean } | null = null;

// Print da área de membros, ex.: "/area-de-membros.png" (arquivo em public/).
// Deixe null para mostrar o espaço reservado.
export const PLATFORM_SCREENSHOT: string | null = null;
