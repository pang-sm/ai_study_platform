import type { ComponentProps } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/lib/utils';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-hover',
  secondary:
    'bg-surface text-text-primary border border-border-default hover:bg-primary-soft',
  ghost: 'text-text-secondary hover:bg-primary-soft hover:text-text-primary',
  danger: 'bg-danger text-white hover:bg-danger/90',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-metadata',
  md: 'h-10 px-4 text-body',
  lg: 'h-12 px-5 text-body',
};

export interface ButtonProps extends ComponentProps<'button'> {
  asChild?: boolean;
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({
  asChild = false,
  variant = 'primary',
  size = 'md',
  className,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : 'button';
  return (
    <Comp
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-control font-medium',
        'transition-colors duration-fast ease-standard',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
        'disabled:pointer-events-none disabled:opacity-50',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...(asChild ? {} : { type: 'button' })}
      {...props}
    />
  );
}
