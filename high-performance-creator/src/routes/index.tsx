import { createFileRoute } from "@tanstack/react-router";

import {
  About,
  Faq,
  Footer,
  Header,
  Hero,
  Included,
  Learn,
  Offer,
  Platform,
  Proof,
  StickyBar,
} from "@/components/hpc/sections";
import { useCtaVisibility, useRevealOnScroll } from "@/hooks/use-landing";

export const Route = createFileRoute("/")({
  component: Index,
  head: () => ({
    meta: [
      { title: "High Performance Creator | Mentoria para UGC Creators" },
      {
        name: "description",
        content:
          "O método para transformar seu Instagram em um canal de aquisição de clientes e criar mais previsibilidade como UGC Creator.",
      },
      { property: "og:title", content: "High Performance Creator | Mentoria para UGC Creators" },
      {
        property: "og:description",
        content:
          "Seja vista, lembrada e receba mais oportunidades com um perfil que vende o seu trabalho.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
});

function Index() {
  const showCta = useCtaVisibility();
  useRevealOnScroll();

  return (
    <div className="relative overflow-x-clip bg-background text-foreground">
      <a href="#conteudo" className="skip-link">
        Ir para o conteúdo
      </a>
      <Header showCta={showCta} />
      <main id="conteudo">
        <Hero />
        <Proof />
        <Learn />
        <Platform />
        <About />
        <Included />
        <Offer />
        <Faq />
      </main>
      <Footer />
      <StickyBar visible={showCta} />
    </div>
  );
}
