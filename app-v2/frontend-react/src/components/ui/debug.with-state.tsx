import { useGlobalDebugVisibility } from "#/state/global.debug-visibility";

/** React Component - Render children if debug mode is enabled */
export function DebugOnly({ children }: { children: React.ReactNode; }) {
  const debugApi = useGlobalDebugVisibility();
  if (!debugApi.isVisible) {
    return null;
  }
  return <>{children}</>;
}
