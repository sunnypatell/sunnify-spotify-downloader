import os from "node:os";
import path from "node:path";

export const utilsPath = {
  /**
   * Get current working directory
   */
  getCWD() {
    return process.cwd();
  },
  /**
   * Get user home directory  
   * Mac: `/Users/username`  
   * Windows: `C:\Users\username`  
   * Linux: `/home/username`  
   */
  getUserHomeDir() {
    return os.homedir();
  },
  /**
   * Get user desktop directory  
   * Mac: `/Users/username/Desktop`  
   * Windows: `C:\Users\username\Desktop`  
   * Linux: `/home/username/Desktop`
   */
  getUserDesktopDir() {
    return path.join(os.homedir(), "Desktop");
  },
};
