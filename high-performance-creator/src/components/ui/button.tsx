import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium cursor-pointer transition-colors touch-manipulation focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50 disabled:cursor-not-allowed [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        // Botão de venda no padrão do TCC: quadrado, azul-marinho, texto creme; sobe 1px no hover.
        sales:
          "rounded-none border border-primary bg-primary text-primary-foreground transition-[opacity,transform] duration-200 hover:-translate-y-px hover:opacity-90 focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-ring",
        // Versão dourada (o "destaque" dos cartões azul-marinho do TCC).
        gold: "rounded-none border border-accent bg-accent text-accent-foreground transition-[opacity,transform] duration-200 hover:-translate-y-px hover:opacity-90 focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-accent",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
        sales:
          "min-h-[52px] px-8 py-3 text-center text-xs font-semibold uppercase leading-snug tracking-[0.1em] whitespace-normal",
        header:
          "min-h-[44px] px-5 text-xs font-semibold uppercase tracking-[0.1em] whitespace-normal",
        bar: "min-h-12 px-4 text-center text-[0.6875rem] font-semibold uppercase leading-tight tracking-[0.1em] whitespace-normal",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
