const mobileBundle = new URL(import.meta.url).pathname.split("/").pop() || "unknown";

window.MOBILE_BUILD_VERSION = Object.freeze({
  commit: import.meta.env.VITE_MOBILE_BUILD_COMMIT || "unknown",
  bundle: mobileBundle,
});
