import { useRef, useEffect, useCallback } from 'react';

/**
 * Custom hook to prevent state updates on unmounted components
 */
export function useMountedRef() {
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  return isMountedRef;
}

/**
 * Returns a wrapper around async functions that only executes callbacks if the component remains mounted
 */
export function useSafeCallback(callback) {
  const isMountedRef = useMountedRef();

  return useCallback(
    (...args) => {
      if (isMountedRef.current) {
        return callback(...args);
      }
    },
    [callback, isMountedRef]
  );
}
