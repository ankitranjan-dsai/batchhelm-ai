const DEMO_KEY_STORAGE = "batchhelm.demo-key";

export function getDemoKey(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return sessionStorage.getItem(DEMO_KEY_STORAGE) ?? "";
}

export function setDemoKey(key: string): void {
  if (typeof window === "undefined") {
    return;
  }
  sessionStorage.setItem(DEMO_KEY_STORAGE, key);
}

export function clearDemoKey(): void {
  if (typeof window === "undefined") {
    return;
  }
  sessionStorage.removeItem(DEMO_KEY_STORAGE);
}
