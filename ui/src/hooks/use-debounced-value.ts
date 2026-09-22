import { useEffect, useState } from "react";

/**
 * Delay a value until the user stops changing it.
 *
 * Typed inputs (loan rate, processing fee) would otherwise fire one
 * request to the engine per keystroke.
 */
export function useDebouncedValue<T>(value: T, delayMs = 250): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
