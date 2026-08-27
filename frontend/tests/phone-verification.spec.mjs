import { test, expect } from "@playwright/test";

const BASE = "https://101.32.190.42";
const USERNAME = "奶12";

test.describe("phone verification", () => {
  test("invalid phone is rejected with PHONE_INVALID", async ({ request }) => {
    const r = await request.post(`${BASE}/api/me/phone/send-code`, { data: { phone: "123" } });
    expect(r.status()).toBe(400);
    const body = await r.json();
    expect(body.detail.code).toBe("PHONE_INVALID");
  });

  test("valid phone without SMS config returns SMS_SERVICE_NOT_CONFIGURED", async ({ request }) => {
    const r = await request.post(`${BASE}/api/me/phone/send-code`, { data: { phone: "13812345678" } });
    expect(r.status()).toBe(503);
    const body = await r.json();
    expect(body.detail.code).toBe("SMS_SERVICE_NOT_CONFIGURED");
  });

  test("verify without a code is rejected", async ({ request }) => {
    const r = await request.post(`${BASE}/api/me/phone/verify`, { data: { phone: "13812345678", code: "123456" } });
    expect(r.status()).toBe(400);
    const body = await r.json();
    expect(body.detail.code).toBe("PHONE_CODE_INVALID");
  });

  test("response never returns a plaintext code", async ({ request }) => {
    const r = await request.post(`${BASE}/api/me/phone/send-code`, { data: { phone: "13812345678" } });
    const text = await r.text();
    expect(text).not.toContain("verification_code");
    expect(text).not.toContain("plaintext_code");
  });
});
