import { expect, test } from "@playwright/test";

test("la puerta de entrada cabe en escritorio, tablet y móvil", async ({ page }) => {
  await page.goto("/entrar");
  await expect(page.getByRole("heading", { name: "Veta" })).toBeVisible();
  await expect(page.getByLabel("Correo")).toBeVisible();
  await expect(page.getByRole("button", { name: "Entrar al escenario" })).toBeVisible();
});
