import type { CSSProperties } from "react";

// Os números vêm do texto da Layfe: "Em 3 meses, saí de um faturamento de R$ 1 mil para
// R$ 5 mil, R$ 8 mil e R$ 10 mil, respectivamente."
const points = [
  { label: "Antes", value: 1, text: "R$ 1 mil", before: true },
  { label: "Mês 1", value: 5, text: "R$ 5 mil", before: false },
  { label: "Mês 2", value: 8, text: "R$ 8 mil", before: false },
  { label: "Mês 3", value: 10, text: "R$ 10 mil", before: false },
];

const MAX = 10;

export function GrowthChart() {
  return (
    <figure
      data-reveal
      className="rounded-[10px] border border-line-st bg-card p-5 text-foreground sm:p-7"
    >
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-sm font-semibold text-navy sm:text-base">
          Faturamento mensal da Layfe
        </span>
        <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-ink-soft">
          nos 3 primeiros meses
        </span>
      </figcaption>

      {/* O visual é decorativo para leitores de tela: a tabela abaixo carrega os mesmos valores. */}
      <div aria-hidden className="mt-10 grid grid-cols-4 gap-3 sm:gap-6">
        {points.map((point, index) => (
          <div key={point.label} className="flex flex-col items-center">
            <div className="relative flex h-40 w-full items-end justify-center border-b border-line-st sm:h-48">
              <div
                className={
                  point.before
                    ? "bar w-full max-w-14 rounded-t bg-ink-soft/30"
                    : "bar w-full max-w-14 rounded-t bg-navy"
                }
                style={{ height: `${(point.value / MAX) * 100}%`, "--i": index } as CSSProperties}
              />
              <span
                className="bar-label absolute inset-x-0 text-center text-sm font-semibold leading-none text-foreground sm:text-base"
                style={
                  {
                    bottom: `calc(${(point.value / MAX) * 100}% + 10px)`,
                    "--i": index,
                  } as CSSProperties
                }
              >
                {point.text}
              </span>
            </div>
            <span className="mt-3 text-xs font-medium text-ink-soft sm:text-sm">{point.label}</span>
          </div>
        ))}
      </div>

      {/* A div faz o "esconder visualmente" funcionar: tabela sozinha ignora width/overflow. */}
      <div className="sr-only">
        <table>
          <caption>Faturamento mensal da Layfe antes da estratégia e nos 3 primeiros meses</caption>
          <thead>
            <tr>
              <th scope="col">Período</th>
              <th scope="col">Faturamento</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.label}>
                <th scope="row">{point.label}</th>
                <td>{point.text}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
