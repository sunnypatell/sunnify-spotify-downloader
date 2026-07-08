import { atom, useAtom } from "jotai";

const atomDebugIsVisible = atom<boolean>(false);

export const useGlobalDebugVisibility = () => {
  const [isVisible, setIsVisible] = useAtom(atomDebugIsVisible);
  const toggleIsVisible = () => setIsVisible(prev => !prev);
  return {
    isVisible,
    setIsVisible,
    toggleIsVisible,
  };
};