import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** shadcn/ui 约定的 class 合并:后写的 Tailwind 类覆盖先写的同族类。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
