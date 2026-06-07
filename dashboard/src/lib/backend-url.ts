const DEFAULT_BACKEND_URL = "http://127.0.0.1:13243";

export const backendUrl =
  process.env.MODELPORT_BACKEND_URL ??
  process.env.NEXT_PUBLIC_MODELPORT_BACKEND_URL ??
  DEFAULT_BACKEND_URL;
