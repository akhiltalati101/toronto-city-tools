import { useEffect, useId, useRef, useState } from "react";
import type { LocationQuery } from "../lib/types";

// Photon (the same geocoder the API uses) straight from the browser for
// type-ahead suggestions, limited to Toronto. Picking a suggestion sends its
// coordinates, so the API doesn't geocode again. If Photon is unreachable the
// box still works as a plain address field.
const PHOTON_URL = "https://photon.komoot.io/api/";
const TORONTO_BBOX = "-79.64,43.58,-79.11,43.86";

interface Suggestion {
  label: string;
  detail: string;
  lat: number;
  lon: number;
}

interface PhotonFeature {
  geometry: { coordinates: [number, number] };
  properties: Record<string, string | undefined>;
}

function toSuggestion(f: PhotonFeature): Suggestion {
  const p = f.properties;
  const street = [p.housenumber, p.street].filter(Boolean).join(" ");
  const label = p.name && p.name !== street ? (street ? `${p.name}, ${street}` : p.name) : street || p.name || "Unnamed place";
  const detail = [p.district ?? p.locality, p.city ?? "Toronto", p.postcode].filter(Boolean).join(", ");
  return { label, detail, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0] };
}

export function AddressSearch({
  initial = "",
  onSubmit,
  label = "Address",
  placeholder = "e.g. 100 Queen St W",
  submitLabel = "Check it",
  busy = false,
  hideButton = false,
}: {
  initial?: string;
  onSubmit: (q: LocationQuery) => void;
  label?: string;
  placeholder?: string;
  submitLabel?: string;
  busy?: boolean;
  hideButton?: boolean;
}) {
  const [text, setText] = useState(initial);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  const skipNextFetch = useRef(false);
  const id = useId();

  // Follow the URL when it changes underneath us (back button, map click).
  useEffect(() => {
    skipNextFetch.current = true;
    setText(initial);
  }, [initial]);

  useEffect(() => {
    if (skipNextFetch.current) {
      skipNextFetch.current = false;
      return;
    }
    const q = text.trim();
    if (q.length < 3) {
      setSuggestions([]);
      return;
    }
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q, limit: "6", lang: "en", bbox: TORONTO_BBOX });
        const resp = await fetch(`${PHOTON_URL}?${params}`, { signal: ctrl.signal });
        const body = (await resp.json()) as { features: PhotonFeature[] };
        setSuggestions(body.features.map(toSuggestion));
        setActive(-1);
        setOpen(true);
      } catch {
        // offline / blocked / aborted: no suggestions, plain field still works
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [text]);

  const choose = (s: Suggestion) => {
    skipNextFetch.current = true;
    setText(s.label);
    setOpen(false);
    onSubmit({ address: s.label, lat: s.lat, lon: s.lon });
  };

  const submitText = () => {
    setOpen(false);
    if (text.trim()) onSubmit({ address: text.trim() });
  };

  const showList = open && suggestions.length > 0;

  return (
    <form
      role="search"
      className="relative"
      onSubmit={(e) => {
        e.preventDefault();
        if (showList && active >= 0) choose(suggestions[active]);
        else submitText();
      }}
    >
      <label htmlFor={`${id}-input`} className="mb-1 block text-sm font-medium text-ink-2">
        {label}
      </label>
      <div className="flex gap-2">
        <input
          id={`${id}-input`}
          type="text"
          role="combobox"
          aria-expanded={showList}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? `${id}-opt-${active}` : undefined}
          autoComplete="off"
          value={text}
          placeholder={placeholder}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
          }}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (!showList) return;
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => (a + 1) % suggestions.length);
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => (a <= 0 ? suggestions.length - 1 : a - 1));
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
        />
        {!hideButton && (
          <button
            type="submit"
            disabled={busy || !text.trim()}
            className="shrink-0 rounded-lg bg-accent px-4 py-2 font-semibold text-accent-ink hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Checking…" : submitLabel}
          </button>
        )}
      </div>
      {showList && (
        <ul
          id={`${id}-list`}
          role="listbox"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-line bg-surface py-1 shadow-lg"
        >
          {suggestions.map((s, i) => (
            <li
              key={`${s.lat},${s.lon},${i}`}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(s);
              }}
              onMouseEnter={() => setActive(i)}
              className={`cursor-pointer px-3 py-2 text-sm ${i === active ? "bg-surface-2" : ""}`}
            >
              <div className="font-medium text-ink">{s.label}</div>
              <div className="text-xs text-ink-muted">{s.detail}</div>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
