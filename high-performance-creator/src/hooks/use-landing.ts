import { useEffect, useState } from "react";

// Mostra os botões fixos (cabeçalho no desktop, barra no celular) só quando o botão do topo
// saiu da tela e a oferta ainda não está visível, para o botão não aparecer duplicado.
export function useCtaVisibility() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const hero = document.getElementById("cta-hero");
    const offer = document.getElementById("inscricao");
    if (!hero || !offer || !("IntersectionObserver" in window)) return;

    let heroInView = true;
    let offerInView = false;
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.target === hero) heroInView = entry.isIntersecting;
        else offerInView = entry.isIntersecting;
      }
      setVisible(!heroInView && !offerInView);
    });
    observer.observe(hero);
    observer.observe(offer);
    return () => observer.disconnect();
  }, []);

  return visible;
}

// Blocos com data-reveal aparecem suavemente quando entram na tela.
export function useRevealOnScroll() {
  useEffect(() => {
    const elements = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
    if (!("IntersectionObserver" in window)) {
      elements.forEach((el) => el.classList.add("is-in"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 },
    );
    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
}
