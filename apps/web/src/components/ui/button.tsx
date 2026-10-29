import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "cn";

/**
 * Buttons press to 0.97 scale (the `pressable` utility, plain CSS, so it works in
 * server-rendered markup too). See docs/DESIGN.md.
 */
const buttonVariants = cva(
  "group/button inline-flex shrink-0 pressable items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap outline-none select-none focus-visible:ring-3 focus-visible:ring-ring/40 disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-card hover:bg-[color-mix(in_oklab,var(--primary),black_12%)]",
        soft: "bg-primary-soft text-primary-soft-foreground hover:bg-[color-mix(in_oklab,var(--primary-soft),var(--primary)_10%)]",
        outline:
          "border-border bg-card text-foreground shadow-card hover:bg-muted aria-expanded:bg-muted",
        secondary:
          "bg-muted text-foreground hover:bg-[color-mix(in_oklab,var(--muted),var(--foreground)_6%)] aria-expanded:bg-muted",
        ghost:
          "text-foreground hover:bg-muted aria-expanded:bg-muted aria-[current=page]:bg-primary-soft aria-[current=page]:text-primary-soft-foreground",
        destructive:
          "bg-urgent text-white shadow-card hover:bg-[color-mix(in_oklab,var(--urgent),black_12%)] focus-visible:ring-urgent/30 dark:text-[#1a0606]",
        "destructive-soft":
          "bg-urgent-soft text-urgent-foreground hover:bg-[color-mix(in_oklab,var(--urgent-soft),var(--urgent)_10%)]",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-9 gap-1.5 px-3.5 has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        xs: "h-7 gap-1 rounded-md px-2.5 text-xs [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1.5 rounded-[10px] px-3 text-[13px] [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-10 gap-2 px-4 text-[15px]",
        xl: "h-12 gap-2 rounded-xl px-5 text-[17px] [&_svg:not([class*='size-'])]:size-5",
        icon: "size-9",
        "icon-xs": "size-7 rounded-md [&_svg:not([class*='size-'])]:size-3.5",
        "icon-sm": "size-8 rounded-[10px]",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
