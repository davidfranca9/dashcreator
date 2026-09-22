# Avaliação UX da página High Performance Creator

Avaliação feita como UI/UX designer sobre o projeto `high-performance-creator-ajustado.zip`.
**Todo o texto é o original** (só dois travessões do FAQ viraram vírgula). Comparativos em
[avaliacao/antes-e-depois.png](avaliacao/antes-e-depois.png) (primeira rodada, em azul e amarelo) e
[avaliacao/identidade-tcc-vs-hpc.png](avaliacao/identidade-tcc-vs-hpc.png) (identidade atual).

## Como rodar

```sh
cd high-performance-creator
npm install     # só na primeira vez
npm run dev     # abre em http://localhost:8080
npm run build   # versão de produção
```

## Identidade visual: agora casa com a The Creators Club

A primeira versão usava azul elétrico, amarelo e Montserrat com sombras duras. O site do TCC
(`landing/index.html`, fonte de verdade) é outro universo: papel creme, azul-marinho, dourado,
títulos em Playfair Display e texto em Inter, botões quadrados e linhas finas. A HPC foi refeita
nesse padrão, sem mudar layout nem texto:

| | TCC (referência) | HPC antes | HPC agora |
| --- | --- | --- | --- |
| Fundo | creme `#f5f1e8` e `#eae4d4` | creme com azul suave | igual ao TCC |
| Cor principal | azul-marinho `#0a2463` | azul elétrico `#006afe` | azul-marinho `#0a2463` |
| Destaque | dourado `#c9956a` | amarelo | dourado `#c9956a` |
| Títulos | Playfair Display, última frase em itálico dourado | Montserrat 600 | igual ao TCC |
| Texto | Inter | Montserrat | Inter |
| Botão | quadrado, azul-marinho; dourado no cartão de destaque | retângulo azul com sombra dura | igual ao TCC |
| Cartões | cantos de 10px, linha fina, sem sombra dura | quadrados com sombra dura | igual ao TCC |

O cartão da oferta virou o mesmo "destaque" dos caminhos do TCC: fundo azul-marinho e botão dourado.
Os cantos de visor de câmera que ficaram no topo e no vídeo são o desenho do próprio logo do TCC.

**Contraste:** o dourado exato só passa sobre o azul-marinho (5,5:1). Sobre o creme ele daria 2,3:1,
então texto e itálicos usam tons mais fechados da mesma família (`--gold-deep` e `--gold-ink` em
`src/styles.css`). Fica visivelmente dourado, mas passa na auditoria.

Para voltar à paleta anterior: `avaliacao/versao-anterior-azul-e-amarelo.zip` guarda os arquivos de antes.

## Logo

O zip original trazia só uma referência expirada ao logo (`hpc-logo.png` no Lovable). O
`favicon.png` dele mostrava o desenho: "High Performance" sobre "Creator", com o "C" de play e os
cantos de visor do TCC. Com base nisso o logo foi **remontado a partir dos glifos oficiais do logo
do TCC** ("Creator" sem o "s" e os cantos), com "High Performance" em cima.

- `public/hpc-logo.png`: versão para fundo claro (cabeçalho).
- `public/hpc-logo-claro.png`: versão para fundo escuro (rodapé).
- `public/favicon.png` e `favicon.ico`: o "C" com play. O `.ico` antigo era o coração padrão do Lovable.

É provisório: se você tiver o arquivo original, é só salvar por cima com os mesmos nomes.

## Títulos em duas linhas

Todo título de seção (e os 7 dos cards do programa) tem exatamente duas linhas, com quebra
escolhida no sentido da frase (por exemplo "Transforme seu Instagram / em um *ímã de marcas.*").
O tamanho da letra se ajusta sozinho à largura, então nada estoura.

| Largura | Comportamento |
| --- | --- |
| 1024 px ou mais | todos em duas linhas (só "FAQ" fica em uma, por ser uma palavra) |
| 768 a 1023 px | duas linhas, exceto o título do depoimento (89 caracteres), que fecha em 2 linhas só a partir de 1024 px |
| celular | os curtos ficam em duas linhas; os longos quebram naturalmente, porque em 390 px duas linhas deixariam a letra minúscula |

Implementação: componente `Title` em `src/components/hpc/primitives.tsx`. A largura de cada linha
(`em`) foi medida com a fonte real; se trocar o texto de um título, é só remedir e ajustar o `em`.

## O que estava errado (primeira avaliação)

| Área | Problema |
| --- | --- |
| Identidade | Não casava com a do TCC (ver seção acima) |
| Contraste | Rótulos azuis sobre azul-marinho a 3,2:1, texto branco a 85% sobre azul a 3,7:1 |
| Leitura | Tudo centralizado, inclusive parágrafos de 5 linhas |
| Cards do programa | 7 cards em 3 colunas deixavam o 7º sozinho; no celular ocupavam 2211px |
| Confiança | A página vende a autoridade da Layfe e não mostrava o rosto dela |
| Prova | Os números do faturamento estavam escondidos no meio de um parágrafo |
| Fluxo | A oferta vinha antes de "Quem vai te guiar" |
| Conversão | 3 botões iguais e nenhum botão fixo numa página longa de celular |
| Acessibilidade | Foco de teclado invisível, sem "pular para o conteúdo", `lang="en"` numa página em português |
| Detalhes | `twitter:site` = @Lovable, telas de erro em inglês, botão da oferta apontando para ela mesma |

## O que mudou (além da identidade, do logo e dos títulos)

- **Hero:** foto pequena da Layfe e três fatos tirados do próprio texto (04 encontros ao vivo,
  segundas às 19h, 45 dias de acesso). O botão principal cabe na primeira tela do celular.
- **Programa:** grade 4 + 3 no desktop, lista compacta no celular (2211px caiu para cerca de 1500px).
- **Quem vai te guiar:** foto real da Layfe (a do site dela, otimizada de 1,3 MB para 110 KB) e um
  gráfico simples com os números que ela mesma cita.
- **Ordem:** "Quem vai te guiar" vem antes de "Tudo que está incluso" e da oferta. Para desfazer,
  mova `<About />` em `src/routes/index.tsx`.
- **Botões:** botão no cabeçalho (desktop) e barra fixa com o preço (celular), que some quando a
  oferta está na tela; anel de foco visível.
- **FAQ:** cartões com ícone de mais/menos, um aberto por vez, alvo de toque de 64px.
- **Movimento:** entrada suave, desligada com `prefers-reduced-motion` e sempre visível sem JavaScript.
- **Base:** `lang="pt-BR"`, link "Ir para o conteúdo", marcos (`header`, `main`, `footer`), telas de
  erro em português, `twitter:site` removido.

Verificação: axe-core (WCAG 2.1 AA) com 0 violações no desktop e no celular, build de produção e
ESLint sem erros, 13 testes de comportamento (barra fixa, teclado, FAQ, movimento reduzido, sem JavaScript).

## O que falta com você

Tudo isso fica em `src/config.ts`, com instruções nos comentários:

1. **Logo original da HPC**, se existir (ver seção Logo).
2. **Link do checkout** (`CHECKOUT_URL`). Hoje o botão da oferta ainda aponta para `#inscricao`.
3. **Vídeo do depoimento** (`TESTIMONIAL_VIDEO`) e **print da área de membros** (`PLATFORM_SCREENSHOT`).
4. **Rodapé:** termos, privacidade, contato/WhatsApp e CNPJ ainda não existem na página.
5. **Imagem de compartilhamento** (`og:image`): sem ela o link no WhatsApp aparece sem prévia.

## Para conferir

- O gráfico rotula as colunas "Antes, Mês 1, Mês 2, Mês 3". Isso vem de "em 3 meses, saí de
  R$ 1 mil para R$ 5 mil, R$ 8 mil e R$ 10 mil, respectivamente". Se não for essa a leitura, ajuste
  `points` em `src/components/hpc/growth-chart.tsx` (ou remova o gráfico).
- A etiqueta da foto diz "Layfe · Mentora da HPC".
- 12x de R$ 60,66 soma R$ 727,92, ou seja, o parcelado tem acréscimo sobre os R$ 597 à vista.
  Vale deixar isso claro no texto do preço.
