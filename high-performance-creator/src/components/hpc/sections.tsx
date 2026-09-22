import * as AccordionPrimitive from "@radix-ui/react-accordion";
import {
  CalendarDays,
  Check,
  Clock,
  LayoutDashboard,
  Minus,
  Play,
  Plus,
  Target,
  Video,
} from "lucide-react";

import { Accordion, AccordionContent, AccordionItem } from "@/components/ui/accordion";
import { CHECKOUT_URL, PLATFORM_SCREENSHOT, TESTIMONIAL_VIDEO } from "@/config";
import { asset } from "@/lib/asset";
import { faq, included, modules } from "@/lib/content";
import { heroDelay, revealDelay } from "@/lib/landing";
import { cn } from "@/lib/utils";

import { GrowthChart } from "./growth-chart";
import { Accent, Eyebrow, SalesButton, Title } from "./primitives";

const facts = [
  { Icon: Video, label: "04 encontros ao vivo" },
  { Icon: CalendarDays, label: "Segundas, às 19h" },
  { Icon: Clock, label: "45 dias de acesso" },
];

/* -------------------------------------------------------------------------- */
/*  Cabeçalho e barra fixa                                                    */
/* -------------------------------------------------------------------------- */

export function Header({ showCta }: { showCta: boolean }) {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5 sm:h-[72px] sm:px-8">
        <a
          href="#top"
          aria-label="High Performance Creator, voltar ao topo"
          className="flex shrink-0 items-center"
        >
          <img
            src={asset("/hpc-logo.png")}
            alt=""
            width={817}
            height={346}
            className="h-11 w-auto sm:h-14"
          />
        </a>

        <div
          inert={!showCta}
          className={cn(
            "hidden transition-opacity duration-200 md:block",
            showCta ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        >
          <SalesButton size="header">Quero mudar meu jogo</SalesButton>
        </div>
      </div>
    </header>
  );
}

// No celular, o botão principal acompanha a rolagem: a página é longa e o toque precisa estar à mão.
export function StickyBar({ visible }: { visible: boolean }) {
  return (
    <div
      inert={!visible}
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      className={cn(
        "fixed inset-x-0 bottom-0 z-50 border-t border-line-st bg-background/95 backdrop-blur-md transition-transform duration-300 md:hidden",
        visible ? "translate-y-0" : "translate-y-full",
      )}
    >
      <div className="flex items-center gap-4 px-4 pb-3 pt-3">
        <p className="shrink-0 leading-none">
          <span className="display-type block text-[1.625rem] font-medium text-navy">R$ 597</span>
          <span className="mt-1 block text-[0.7rem] font-medium text-ink-soft">
            12x de R$ 60,66
          </span>
        </p>
        <SalesButton size="bar" className="flex-1">
          Quero mudar meu jogo
        </SalesButton>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Topo                                                                      */
/* -------------------------------------------------------------------------- */

export function Hero() {
  return (
    <section id="top" className="relative">
      <div className="mx-auto max-w-6xl px-5 pb-12 pt-6 sm:px-8 sm:pb-20 sm:pt-8">
        <div className="relative px-2 py-8 text-center sm:px-8 sm:py-10 lg:px-14">
          <span aria-hidden className="corner-frame pointer-events-none absolute inset-0" />

          <div className="flex flex-col items-center">
            <p
              style={heroDelay(0)}
              className="hero-in inline-flex items-center gap-2.5 rounded-full border border-line-st px-4 py-2 text-[0.625rem] font-semibold uppercase tracking-[0.2em] text-ink-soft"
            >
              <span aria-hidden className="size-1.5 rounded-full bg-gold" />
              Edição especial Black Friday
            </p>

            <div style={heroDelay(80)} className="hero-in mt-6 w-full">
              <Title
                as="h1"
                from="md"
                max="4.25rem"
                em={11.9}
                className="[--min:2.25rem] [--vw:9vw]"
                lines={[
                  "Transforme seu Instagram",
                  <>
                    em um <Accent>ímã de marcas.</Accent>
                  </>,
                ]}
              />
            </div>

            <p
              style={heroDelay(200)}
              className="hero-in mt-6 max-w-3xl text-pretty text-base leading-relaxed text-ink-soft sm:text-lg"
            >
              UGC não precisa postar os trabalhos que faz para as marcas, mas uma UGC que performa é
              constante nas redes sociais e cria conteúdo estratégico para ser notada pelas marcas,
              receber inbounds e ter previsibilidade.
            </p>
            <p
              style={heroDelay(280)}
              className="hero-in mt-3 max-w-3xl text-pretty text-base font-medium leading-relaxed text-foreground sm:text-lg"
            >
              É uma estrutura que vai funcionar por você. Vai vender você antes mesmo de a marca
              entrar em contato.
            </p>

            <div style={heroDelay(360)} className="hero-in mt-7 w-full sm:w-auto">
              <SalesButton id="cta-hero" className="w-full sm:w-auto" />
            </div>

            <div
              style={heroDelay(460)}
              className="hero-in mt-9 flex flex-wrap items-center justify-center gap-x-8 gap-y-4"
            >
              <div className="flex items-center gap-3 text-left">
                <img
                  src={asset("/layfe-avatar.jpg")}
                  alt=""
                  width={44}
                  height={44}
                  className="size-11 rounded-lg border border-line-st object-cover"
                />
                <p className="text-sm leading-tight">
                  <span className="block font-semibold text-navy">Mentoria com a Layfe</span>
                  <span className="block text-ink-soft">Em grupo e ao vivo</span>
                </p>
              </div>
              <ul className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm font-medium text-ink-soft">
                {facts.map(({ Icon, label }) => (
                  <li key={label} className="flex items-center gap-2">
                    <Icon className="size-4 text-gold-deep" aria-hidden />
                    {label}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/*  Prova: depoimento em vídeo                                                */
/* -------------------------------------------------------------------------- */

function isEmbed(src: string) {
  return /youtube\.com\/embed|youtube-nocookie\.com\/embed|player\.vimeo\.com/.test(src);
}

function TestimonialVideo() {
  const video = TESTIMONIAL_VIDEO;

  return (
    <div className={cn("relative mx-auto", video?.vertical ? "max-w-xs" : "max-w-3xl")}>
      <span aria-hidden className="corner-frame pointer-events-none absolute -inset-3" />
      <div
        className={cn(
          "relative overflow-hidden rounded-lg bg-[oklch(0.22_0.1_264)] ring-1 ring-primary-foreground/15",
          video?.vertical ? "aspect-[9/16]" : "aspect-video",
        )}
      >
        {video ? (
          isEmbed(video.src) ? (
            <iframe
              src={asset(video.src)}
              title="Depoimento de uma aluna da mentoria"
              loading="lazy"
              allow="accelerometer; autoplay; encrypted-media; picture-in-picture"
              allowFullScreen
              className="absolute inset-0 size-full"
            />
          ) : (
            <video
              controls
              playsInline
              preload="metadata"
              poster={video.poster ? asset(video.poster) : undefined}
              className="absolute inset-0 size-full object-cover"
            >
              <source src={asset(video.src)} />
            </video>
          )
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 p-6">
            <span className="grid size-16 place-items-center rounded-full bg-gold text-accent-foreground sm:size-20">
              <Play className="size-7 fill-current sm:size-8" aria-hidden />
            </span>
            <p className="text-sm font-medium text-primary-foreground/75">
              Espaço reservado para o vídeo de depoimento
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export function Proof() {
  return (
    <section
      aria-labelledby="prova-title"
      className="on-dark bg-secondary py-16 text-secondary-foreground sm:py-24"
    >
      <div className="mx-auto max-w-6xl px-5 text-center sm:px-8">
        <div data-reveal>
          <Eyebrow tone="dark">Seu perfil pode trabalhar por você!</Eyebrow>
        </div>
        <div data-reveal className="mt-5" style={revealDelay(80)}>
          <Title
            id="prova-title"
            tone="dark"
            from="lg"
            em={22.6}
            lines={[
              <>
                Ela entrou na mentoria e, <Accent tone="dark">em 2 semanas</Accent>,
              </>,
              <>
                mesmo sem ter portfólio, <Accent tone="dark">fechou um contrato anual.</Accent>
              </>,
            ]}
          />
        </div>
        <div data-reveal className="mt-14" style={revealDelay(120)}>
          <TestimonialVideo />
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/*  Conteúdo                                                                  */
/* -------------------------------------------------------------------------- */

export function Learn() {
  return (
    <section id="programa" aria-labelledby="programa-title" className="bg-paper-dk py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <div data-reveal className="text-center">
          <Title
            id="programa-title"
            em={5.4}
            lines={[
              "O que você",
              <>
                vai <Accent>aprender</Accent>
              </>,
            ]}
          />
        </div>

        {/* 7 módulos: 4 + 3 no desktop, 2 colunas no tablet, lista compacta no celular. */}
        <ol className="mt-10 grid gap-3 sm:mt-14 sm:grid-cols-2 sm:gap-4 lg:grid-cols-12">
          {modules.map((module, index) => (
            <li
              key={module.number}
              data-reveal
              style={revealDelay((index % 4) * 70)}
              className={cn(
                index < 4 ? "lg:col-span-3" : "lg:col-span-4",
                index === modules.length - 1 && "sm:col-span-2",
              )}
            >
              <div className="grid h-full grid-cols-[3rem_1fr] content-start items-center gap-x-4 gap-y-3 rounded-[10px] border border-line bg-background p-5 sm:p-6 lg:grid-cols-1 lg:items-start lg:gap-y-4">
                <span className="display-type text-[2rem] italic leading-none text-gold-deep">
                  {module.number}
                </span>
                <h3 className="display-type text-[1.375rem] font-medium leading-tight text-navy sm:text-2xl sm:[&>span]:block">
                  <span>{module.lines[0]}</span> <span>{module.lines[1]}</span>
                </h3>
                <p className="col-span-2 text-[0.9375rem] leading-relaxed text-ink-soft lg:col-span-1">
                  {module.description}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Platform() {
  return (
    <section aria-labelledby="plataforma-title" className="py-16 sm:py-24">
      <div className="mx-auto max-w-5xl px-5 text-center sm:px-8">
        <div data-reveal>
          <Eyebrow>Por dentro da mentoria</Eyebrow>
          <div className="mt-4">
            <Title
              id="plataforma-title"
              em={7.9}
              lines={["Área de membros", <Accent key="hpc">HPC</Accent>]}
            />
          </div>
        </div>

        <div
          data-reveal
          style={revealDelay(100)}
          className="mt-10 overflow-hidden rounded-[10px] border border-line-st bg-card text-left shadow-[0_30px_60px_-30px_oklch(0.288_0.116_264/0.35)] sm:mt-14"
        >
          <div
            aria-hidden
            className="flex items-center gap-1.5 border-b border-line bg-paper-dk px-4 py-3"
          >
            <span className="size-2.5 rounded-full bg-ink-soft/25" />
            <span className="size-2.5 rounded-full bg-ink-soft/25" />
            <span className="size-2.5 rounded-full bg-ink-soft/25" />
          </div>
          {PLATFORM_SCREENSHOT ? (
            <img
              src={asset(PLATFORM_SCREENSHOT)}
              alt="Tela da área de membros da High Performance Creator"
              loading="lazy"
              decoding="async"
              className="block w-full"
            />
          ) : (
            <div className="flex aspect-[16/10] flex-col items-center justify-center gap-4 p-6 text-center">
              <LayoutDashboard className="size-12 text-gold-deep" strokeWidth={1.25} aria-hidden />
              <p className="text-sm font-medium text-ink-soft">
                Espaço reservado para o print da plataforma
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/*  Quem vai te guiar                                                         */
/* -------------------------------------------------------------------------- */

export function About() {
  return (
    <section id="layfe" aria-labelledby="layfe-title" className="bg-paper-dk py-16 sm:py-24">
      <div className="mx-auto grid max-w-6xl gap-12 px-5 sm:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
        <div
          data-reveal
          className="mx-auto w-full max-w-sm lg:sticky lg:top-28 lg:max-w-none lg:self-start"
        >
          <div className="relative">
            <img
              src={asset("/layfe.jpg")}
              alt="Layfe sorrindo, de blusa listrada em azul e branco"
              width={900}
              height={1114}
              loading="lazy"
              decoding="async"
              className="aspect-square w-full rounded-lg object-cover object-[50%_18%] lg:aspect-[4/5]"
            />
            <p className="absolute bottom-5 left-5 bg-navy px-4 py-2.5 text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-primary-foreground">
              Layfe · Mentora da HPC
            </p>
          </div>
        </div>

        <div>
          <div data-reveal>
            <Eyebrow>Quem vai te guiar?</Eyebrow>
            <div className="mt-4">
              <Title
                id="layfe-title"
                em={6.4}
                className="text-left"
                lines={[
                  "Prazer,",
                  <>
                    eu sou a <Accent>Layfe!</Accent>
                  </>,
                ]}
              />
            </div>
          </div>

          <div className="mt-8 space-y-5 text-pretty text-[1.0625rem] leading-[1.75] text-ink-soft sm:text-lg">
            <p data-reveal>
              Assim como você, eu cheguei a um momento da minha vida em que sentia que estava
              perdendo tempo. Via dar certo para todo mundo, menos para mim. Eu não entendia o que
              estava fazendo de errado e não gostava de abordar marcas.
            </p>
            <p data-reveal>
              Enquanto todo mundo recebia propostas, o meu perfil continuava no limbo do
              esquecimento. Tudo mudou quando passei a gerenciar o meu perfil como uma empresa.
            </p>
            <p data-reveal>
              Em 3 meses, saí de um faturamento de R$&nbsp;1&nbsp;mil para{" "}
              <strong className="font-semibold text-foreground">
                R$&nbsp;5&nbsp;mil, R$&nbsp;8&nbsp;mil e R$&nbsp;10&nbsp;mil
              </strong>
              , respectivamente. Quando bati a minha meta, saí do CLT.
            </p>

            <div className="py-3">
              <GrowthChart />
            </div>

            <p data-reveal>
              Ter um perfil de impacto foi o que me permitiu sair do CLT. Depois de validar meu
              método e conquistar a liberdade de viver 100% do digital, coloquei toda essa estrutura
              dentro da Mentoria High Performance Creator.
            </p>
            <p
              data-reveal
              className="display-type border-l-2 border-gold pl-5 text-2xl italic leading-snug text-navy sm:text-[1.75rem]"
            >
              A HPC veio para transformar creators nas profissionais mais bem requisitadas pelas
              marcas.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/*  O que está incluso e oferta                                               */
/* -------------------------------------------------------------------------- */

export function Included() {
  return (
    <section
      id="incluso"
      aria-labelledby="incluso-title"
      className="on-dark bg-secondary py-16 text-secondary-foreground sm:py-24"
    >
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <div data-reveal className="mx-auto max-w-4xl text-center">
          <Eyebrow tone="dark">Tudo que está incluso</Eyebrow>
          <div className="mt-4">
            <Title
              id="incluso-title"
              tone="dark"
              from="md"
              em={16.7}
              lines={[
                "Transforme o seu perfil no Instagram",
                <>
                  em um <Accent tone="dark">canal de aquisição de clientes!</Accent>
                </>,
              ]}
            />
          </div>
          <p className="mt-5 text-lg text-primary-foreground/80">
            Tudo que você precisa para fazer o seu perfil vender por você.
          </p>
        </div>

        <ul className="mx-auto mt-10 grid max-w-5xl gap-3 sm:mt-14 sm:grid-cols-2 sm:gap-4">
          {included.map((item, index) => (
            <li
              key={item}
              data-reveal
              style={revealDelay((index % 2) * 70)}
              className="flex items-start gap-4 rounded-[10px] border border-primary-foreground/15 bg-primary-foreground/5 p-4 sm:p-5"
            >
              <span className="mt-px grid size-6 shrink-0 place-items-center rounded-full border border-gold bg-gold/15 text-gold">
                <Check className="size-3.5" strokeWidth={2.5} aria-hidden />
              </span>
              <span className="font-medium leading-snug">{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// O cartão azul-marinho com botão dourado é o mesmo "destaque" dos caminhos do site do TCC.
export function Offer() {
  return (
    <section id="inscricao" aria-labelledby="oferta-title" className="py-16 sm:py-24">
      <div className="mx-auto max-w-4xl px-5 sm:px-8">
        <div
          data-reveal
          className="on-dark rounded-xl bg-secondary p-6 text-center text-secondary-foreground shadow-[0_40px_80px_-40px_oklch(0.288_0.116_264/0.6)] sm:p-12"
        >
          <div className="flex flex-col items-center">
            <p className="bg-gold px-3.5 py-2 text-[0.625rem] font-bold uppercase tracking-[0.14em] text-accent-foreground">
              Última turma antes da Black Friday
            </p>
            <div className="mt-6 w-full">
              <Title
                id="oferta-title"
                tone="dark"
                max="3.5rem"
                em={3.7}
                lines={[
                  "Edição",
                  <Accent key="esp" tone="dark">
                    Especial!
                  </Accent>,
                ]}
              />
            </div>
            <p className="mt-5 max-w-2xl text-pretty leading-relaxed text-primary-foreground/80 sm:text-lg">
              A última oportunidade de entrar na HPC antes da Black Friday e preparar seu perfil,
              seus conteúdos e sua prospecção para um dos períodos mais importantes do ano para as
              marcas.
            </p>

            <div className="mt-9 w-full border-y border-primary-foreground/15 py-8">
              <Eyebrow tone="dark">Investimento</Eyebrow>
              <p className="display-type mt-3 text-[clamp(3.5rem,11vw,5.5rem)] font-medium leading-none text-primary-foreground">
                <span className="align-top text-[0.36em] leading-none">R$</span>
                <span className="ml-1">597</span>
              </p>
              <p className="mt-3 font-medium text-primary-foreground">à vista ou 12x de R$ 60,66</p>
              <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm font-medium text-primary-foreground/80">
                {facts.map(({ Icon, label }) => (
                  <li key={label} className="flex items-center gap-2">
                    <Icon className="size-4 text-gold" aria-hidden />
                    {label}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <SalesButton
            variant="gold"
            href={CHECKOUT_URL}
            className="mt-9 w-full sm:w-auto sm:min-w-96"
          />
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/*  Dúvidas e rodapé                                                          */
/* -------------------------------------------------------------------------- */

export function Faq() {
  return (
    <section id="duvidas" aria-labelledby="faq-title" className="bg-paper-dk py-16 sm:py-24">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 sm:px-8 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] lg:gap-16">
        <div data-reveal className="text-center lg:sticky lg:top-28 lg:self-start lg:text-left">
          <Target
            className="mx-auto size-11 text-gold-deep lg:mx-0"
            strokeWidth={1.25}
            aria-hidden
          />
          <Eyebrow className="mt-5">Tire suas dúvidas</Eyebrow>
          <h2
            id="faq-title"
            className="display-type mt-3 text-[clamp(3rem,7vw,4.5rem)] leading-none text-navy"
          >
            FAQ
          </h2>
          <div className="mt-8 hidden lg:block">
            <SalesButton className="w-full" />
          </div>
        </div>

        <div>
          <Accordion type="single" collapsible defaultValue="faq-0" className="space-y-3">
            {faq.map((item, index) => (
              <AccordionItem
                key={item.question}
                value={`faq-${index}`}
                className="rounded-[10px] border border-line bg-background transition-[border-color,box-shadow] duration-200 data-[state=open]:border-navy data-[state=open]:shadow-[0_24px_48px_-28px_oklch(0.288_0.116_264/0.45)]"
              >
                <AccordionPrimitive.Header className="flex">
                  <AccordionPrimitive.Trigger className="group flex min-h-16 w-full cursor-pointer items-center justify-between gap-4 px-5 py-4 text-left">
                    <span className="display-type text-lg font-medium leading-snug text-navy sm:text-xl">
                      {item.question}
                    </span>
                    <span
                      aria-hidden
                      className="grid size-8 shrink-0 place-items-center rounded-full border border-line-st text-navy transition-colors group-data-[state=open]:border-navy group-data-[state=open]:bg-navy group-data-[state=open]:text-primary-foreground"
                    >
                      <Plus className="size-4 group-data-[state=open]:hidden" />
                      <Minus className="hidden size-4 group-data-[state=open]:block" />
                    </span>
                  </AccordionPrimitive.Trigger>
                </AccordionPrimitive.Header>
                <AccordionContent className="px-5 pb-5 text-base leading-relaxed text-ink-soft">
                  {item.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>

          <div className="mt-10 text-center lg:hidden">
            <SalesButton className="w-full sm:w-auto" />
          </div>
        </div>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="on-dark bg-secondary px-5 pb-32 pt-10 text-secondary-foreground md:pb-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-5 text-center sm:flex-row sm:justify-between sm:text-left">
        <img
          src={asset("/hpc-logo-claro.png")}
          alt="High Performance Creator"
          width={817}
          height={346}
          className="h-14 w-auto"
        />
        <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.16em] text-primary-foreground/70">
          High Performance Creator • The Creators Club
        </p>
      </div>
    </footer>
  );
}
