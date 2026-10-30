"use client";

import { Check, ChevronsUpDown, Loader2, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface ComboboxOption {
  value: string;
  label: string;
  /** Secondary text shown under or beside the label, also searchable. */
  hint?: string;
}

/**
 * Searchable select. Filters `options` locally, or, when `onSearch` is given, hands the
 * typed text to the caller (server-side search) and shows `options` as returned.
 */
export function Combobox({
  id,
  value,
  onChange,
  options,
  placeholder = "Select",
  searchPlaceholder = "Search",
  emptyText = "No matches.",
  selectedLabel,
  onSearch,
  loading,
  clearable,
  clearLabel = "Clear",
  size = "default",
  className,
  "aria-label": ariaLabel,
  "aria-invalid": ariaInvalid,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  options: ComboboxOption[];
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: React.ReactNode;
  /** Label for the current value when it is not among `options` (e.g. async search). */
  selectedLabel?: string;
  onSearch?: (query: string) => void;
  loading?: boolean;
  clearable?: boolean;
  clearLabel?: string;
  size?: "sm" | "default";
  className?: string;
  "aria-label"?: string;
  "aria-invalid"?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value);
  const label = selected?.label ?? (value ? (selectedLabel ?? value) : "");

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={ariaLabel}
          aria-invalid={ariaInvalid}
          className={cn(
            "justify-between bg-card font-normal",
            size === "sm" ? "h-7 text-[13px]" : "h-9",
            !label && "text-muted-foreground",
            value && size === "sm" && "border-primary/50",
            className,
          )}
        >
          <span className="truncate">{label || placeholder}</span>
          <ChevronsUpDown className="ml-1 size-3.5 shrink-0 opacity-50" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-72 p-0" align="start">
        <Command shouldFilter={!onSearch}>
          <CommandInput placeholder={searchPlaceholder} onValueChange={onSearch} />
          <CommandList>
            {loading ? (
              <div className="flex items-center justify-center gap-2 py-6 text-[13px] text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                Searching
              </div>
            ) : (
              <CommandEmpty className="px-3 py-6 text-center text-[13px] text-muted-foreground">{emptyText}</CommandEmpty>
            )}
            {clearable && value && (
              <CommandGroup>
                <CommandItem
                  value="__clear"
                  onSelect={() => {
                    onChange("");
                    setOpen(false);
                  }}
                  className="text-muted-foreground"
                >
                  <X className="size-3.5" aria-hidden="true" />
                  {clearLabel}
                </CommandItem>
              </CommandGroup>
            )}
            <CommandGroup>
              {options.map((o) => (
                <CommandItem
                  key={o.value}
                  value={`${o.label} ${o.hint ?? ""} ${o.value}`}
                  onSelect={() => {
                    onChange(o.value);
                    setOpen(false);
                  }}
                >
                  <Check className={cn("size-3.5 shrink-0", o.value === value ? "opacity-100" : "opacity-0")} aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{o.label}</span>
                    {o.hint && <span className="block truncate text-xs text-muted-foreground">{o.hint}</span>}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
