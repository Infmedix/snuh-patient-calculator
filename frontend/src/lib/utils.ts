import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn/ui 관례의 className 병합 - 조건부 클래스(clsx) + Tailwind 충돌 정리(twMerge). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
