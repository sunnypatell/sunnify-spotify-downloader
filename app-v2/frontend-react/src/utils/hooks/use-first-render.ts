import { useEffect, useState } from "react";

export function useFirstRender() {
  const [firstRender, setFirstRender] = useState(true);
  useEffect(() => {
    setFirstRender(false);
  }, []);
  return firstRender;
}