import type { ComponentProps, CSSProperties, ReactNode } from "react";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CTA_LABEL } from "@/lib/landing";
import { cn } from "@/lib/utils";

type Tone = "light" | "dark";

// Rótulo de seção do TCC: dourado, caixa-alta miúda. Sobre o creme usa o tom fechado (contraste).
export function Eyebrow({
  children,
  tone = "light",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <p className={cn("eyebrow", tone === "light" ? "text-gold-ink" : "text-gold", className)}>
      {children}
    </p>
  );
}

// Trecho em itálico dourado dentro de um título, como "as referências erradas." no site do TCC.
export function Accent({ children, tone = "light" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={cn("italic", tone === "light" ? "text-gold-deep" : "text-gold")}>
      {children}
    </span>
  );
}

// A partir de qual largura o título fica em exatamente duas linhas. Abaixo disso a quebra é natural,
// porque em telas estreitas duas linhas deixariam a letra pequena demais.
type From = "all" | "sm" | "md" | "lg";

const STACK: Record<From, string> = {
  all: "[&>span]:block [&>span]:whitespace-nowrap title-fit",
  sm: "sm:[&>span]:block sm:[&>span]:whitespace-nowrap sm:title-fit",
  md: "md:[&>span]:block md:[&>span]:whitespace-nowrap md:title-fit",
  lg: "lg:[&>span]:block lg:[&>span]:whitespace-nowrap lg:title-fit",
};

// Título em duas linhas. `em` é a largura, em "em", da linha mais comprida (medida com a fonte
// real); o tamanho da letra é o maior que cabe na largura do contêiner, até `max`.
export function Title({
  as: Tag = "h2",
  id,
  lines,
  em,
  max = "3rem",
  from = "all",
  tone = "light",
  className,
}: {
  as?: "h1" | "h2";
  id?: string;
  lines: [ReactNode, ReactNode];
  em: number;
  max?: string;
  from?: From;
  tone?: Tone;
  className?: string;
}) {
  return (
    <div className="@container w-full">
      <Tag
        id={id}
        style={{ "--em": em, "--max": max } as CSSProperties}
        className={cn(
          "display-type text-balance text-[length:clamp(var(--min,1.875rem),var(--vw,6vw),var(--max,3rem))] leading-[1.08]",
          tone === "light" ? "text-navy" : "text-primary-foreground",
          STACK[from],
          className,
        )}
      >
        <span>{lines[0]}</span> <span>{lines[1]}</span>
      </Tag>
    </div>
  );
}

type SalesButtonProps = Omit<ComponentProps<"a">, "children"> & {
  size?: "sales" | "header" | "bar";
  variant?: "sales" | "gold";
  children?: ReactNode;
};

export function SalesButton({
  href = "#inscricao",
  size = "sales",
  variant = "sales",
  className,
  children = CTA_LABEL,
  ...props
}: SalesButtonProps) {
  return (
    <Button asChild variant={variant} size={size} className={className}>
      <a href={href} {...props}>
        {children}
        <ArrowRight
          aria-hidden
          className="transition-transform duration-200 group-hover:translate-x-1"
        />
      </a>
    </Button>
  );
}
