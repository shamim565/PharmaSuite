"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";

import { Input } from "@/components/ui";
import { api } from "@/lib/api";
import { useDebouncedValue } from "@/lib/hooks";
import type { Medicine, Paginated } from "@/lib/types";

function labelFor(medicine: Medicine): string {
  return `${medicine.name}${medicine.strength ? ` ${medicine.strength}` : ""} (${medicine.code})`;
}

export function MedicineCombobox({
  value,
  onChange,
  placeholder = "Search medicine…",
  disabled = false,
  autoFocus = false,
}: {
  value: string;
  onChange: (id: string) => void;
  placeholder?: string;
  disabled?: boolean;
  autoFocus?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [selectedId, setSelectedId] = useState("");
  const [selectedLabel, setSelectedLabel] = useState("");
  const debounced = useDebouncedValue(query, 250);
  const containerRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const { data, isFetching } = useQuery({
    queryKey: ["medicine-combobox", debounced],
    queryFn: () =>
      api.get<Paginated<Medicine>>(
        `/medicines/?page_size=20&is_active=true&search=${encodeURIComponent(debounced)}`,
      ),
    enabled: open,
    staleTime: 30_000,
  });
  const results = data?.results ?? [];

  // Resolve the label for a value set from outside (e.g. edit forms).
  const { data: selectedMedicine } = useQuery({
    queryKey: ["medicine", value],
    queryFn: () => api.get<Medicine>(`/medicines/${value}/`),
    enabled: Boolean(value) && value !== selectedId,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (!value) {
      setSelectedId("");
      setSelectedLabel("");
      setQuery("");
      return;
    }
    if (selectedMedicine && selectedMedicine.id === value) {
      setSelectedId(value);
      setSelectedLabel(labelFor(selectedMedicine));
    }
  }, [value, selectedMedicine]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const select = (medicine: Medicine) => {
    onChange(medicine.id);
    setSelectedId(medicine.id);
    setSelectedLabel(labelFor(medicine));
    setQuery("");
    setOpen(false);
  };

  const activeOptionId =
    open && results[highlight] ? `${listId}-option-${results[highlight].id}` : undefined;

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setHighlight((index) => Math.min(index + 1, Math.max(results.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      if (open && results[highlight]) {
        event.preventDefault();
        select(results[highlight]);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <Input
        role="combobox"
        aria-expanded={open && !disabled}
        aria-controls={`${listId}-listbox`}
        aria-activedescendant={activeOptionId}
        aria-autocomplete="list"
        value={query !== "" ? query : selectedLabel}
        placeholder={placeholder}
        disabled={disabled}
        autoFocus={autoFocus}
        autoComplete="off"
        onFocus={(event) => {
          setOpen(true);
          setHighlight(0);
          event.target.select();
        }}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
          setHighlight(0);
        }}
        onKeyDown={onKeyDown}
      />
      {open && !disabled ? (
        <div
          id={`${listId}-listbox`}
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg"
        >
          {isFetching && results.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-500">Searching…</p>
          ) : null}
          {!isFetching && results.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-500">No medicines match.</p>
          ) : null}
          {results.map((medicine, index) => (
            <button
              type="button"
              key={medicine.id}
              id={`${listId}-option-${medicine.id}`}
              role="option"
              aria-selected={index === highlight}
              onMouseEnter={() => setHighlight(index)}
              onClick={() => select(medicine)}
              className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm ${
                index === highlight ? "bg-primary-50" : "hover:bg-slate-50"
              }`}
            >
              <span className="font-medium text-slate-700">{medicine.name}</span>
              <span className="shrink-0 font-mono text-xs text-slate-500">
                {medicine.code}
                {medicine.strength ? ` · ${medicine.strength}` : ""}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
