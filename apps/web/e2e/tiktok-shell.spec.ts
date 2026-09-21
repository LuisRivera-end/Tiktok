import { expect, test, type Page } from "@playwright/test";

async function register(page: Page) {
  await page.goto("/entrar");
  await page.getByRole("button", { name: "No tengo cuenta" }).click();
  await page.getByLabel("Nombre").fill("Probe");
  await page.getByLabel("Correo").fill(`shell-${Date.now()}-${Math.random().toString(16).slice(2)}@veta.local`);
  await page.getByLabel("Clave").fill("veta1234");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByRole("region", { name: "Escenario de clips" })).toBeVisible();
}

test("riel de acciones, comentarios y marco de teléfono", async ({ page }) => {
  await register(page);
  const stage = page.getByRole("region", { name: "Escenario de clips" });
  await expect(page.getByRole("button", { name: "Me gusta" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Comentarios" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Compartir" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Seguir" })).toBeVisible();

  const box = await stage.boundingBox();
  expect(box, "el escenario debe existir").toBeTruthy();
  if (box && page.viewportSize() && (page.viewportSize()?.width ?? 0) >= 1280) {
    expect(box.width, "columna 9:16, no pantalla completa").toBeLessThan(520);
  }

  const videoId = await stage.getAttribute("data-video-id");
  await page.getByRole("button", { name: "Comentarios" }).click();
  const text = `sesgo-${Date.now()}`;
  await page.getByLabel("Agregar comentario").fill(text);
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(text).first()).toBeVisible();
  await page.goto(`/clip/${videoId}`);
  await expect(page.getByRole("region", { name: "Escenario de clips" })).toBeVisible();
  await page.getByRole("button", { name: "Comentarios" }).click();
  await expect(page.getByText(text).first()).toBeVisible();
});

test("seguir llena Amigos y ocho clips no se van a negro", async ({ page }) => {
  await register(page);
  const stage = page.getByRole("region", { name: "Escenario de clips" });
  await Promise.all([
    page.waitForResponse((res) => res.url().includes("/follows") && res.ok()),
    page.getByRole("button", { name: "Seguir" }).click(),
  ]);
  await page.getByRole("link", { name: "Amigos" }).click();
  await expect(page.getByRole("region", { name: "Escenario de clips" })).toBeVisible({ timeout: 8000 });
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Escenario de clips" })).toBeVisible();
  await page.waitForTimeout(700);

  for (let i = 0; i < 8; i++) {
    const info = await page.evaluate(() => {
      const root = document.querySelector('[aria-label="Escenario de clips"]') as HTMLElement | null;
      if (!root) return null;
      const slides = [...root.querySelectorAll<HTMLElement>("[data-slide]")];
      const active = slides.find((slide) => slide.getAttribute("aria-hidden") === "false") ?? slides[0];
      const transform = getComputedStyle(active).transform;
      const match = transform.match(/matrix\((.+)\)/);
      const ty = match ? Number(match[1].split(",")[5]) : 0;
      return { ty, cat: active.querySelector("[data-poster-category]")?.textContent ?? "" };
    });
    expect(info?.cat.length).toBeGreaterThan(2);
    expect(Math.abs(info?.ty ?? 99)).toBeLessThan(12);
    await page.keyboard.press("j");
    await page.waitForTimeout(700);
  }
});
