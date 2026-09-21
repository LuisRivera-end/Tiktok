import { expect, test, type Page } from "@playwright/test";

async function enterFeed(page: Page) {
  await page.goto("/entrar");
  await page.getByRole("button", { name: "No tengo cuenta" }).click();
  await page.getByLabel("Nombre").fill("Probe");
  await page.getByLabel("Correo").fill(`probe-${Date.now()}-${Math.random().toString(16).slice(2)}@veta.local`);
  await page.getByLabel("Clave").fill("veta1234");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  const stage = page.getByRole("region", { name: "Escenario de clips" });
  await expect(stage).toBeVisible();
  await expect(stage.locator("[data-poster-category]").first()).toBeVisible();
}

async function readSlide(page: Page) {
  return page.evaluate(() => {
    const stage = document.querySelector('[aria-label="Escenario de clips"]') as HTMLElement | null;
    if (!stage) return null;
    const slides = [...stage.querySelectorAll<HTMLElement>("[data-slide]")];
    const active = slides.find((slide) => slide.getAttribute("aria-hidden") === "false") ?? slides[0];
    const stageBox = stage.getBoundingClientRect();
    const slideBox = active.getBoundingClientRect();
    const poster = active.querySelector("[data-poster]") as HTMLElement | null;
    const category = poster?.querySelector("[data-poster-category]")?.textContent ?? "";
    const transform = getComputedStyle(active).transform;
    const match = transform.match(/matrix\((.+)\)/);
    let translateY = 0;
    if (match) {
      const parts = match[1].split(",").map((part) => Number(part.trim()));
      translateY = parts[5] ?? 0;
    }
    const fill = slideBox.height / Math.max(stageBox.height, 1);
    const title =
      [...stage.querySelectorAll("p.font-display")].find((node) => !node.hasAttribute("data-poster-category"))
        ?.textContent ?? "";
    return {
      title,
      category,
      transform,
      translateY,
      fill,
      slideTop: slideBox.top,
      stageTop: stageBox.top,
      slideCount: slides.length,
      posterInStage: slideBox.top < stageBox.bottom && slideBox.bottom > stageBox.top,
    };
  });
}

test("cada clip visible llena el escenario y no se va a negro", async ({ page }) => {
  await enterFeed(page);

  for (let i = 0; i < 8; i++) {
    const info = await readSlide(page);
    expect(info, "el escenario debe tener un slide activo").not.toBeNull();
    if (!info) return;

    expect(info.slideCount, "el feed debe traer varios clips").toBeGreaterThan(3);
    expect(info.posterInStage, `clip "${info.title}" está fuera del escenario`).toBe(true);
    expect(info.fill, `clip "${info.title}" no llena el escenario`).toBeGreaterThan(0.92);
    expect(Math.abs(info.translateY), `clip "${info.title}" está desplazado (ty=${info.translateY})`).toBeLessThan(12);
    expect(info.category.trim().length, `clip "${info.title}" sin categoría en el póster`).toBeGreaterThan(2);
    await expect(page.locator('[data-slide][aria-hidden="false"] [data-poster-category]')).toBeVisible();

    await page.keyboard.press("j");
    await page.waitForTimeout(700);
  }
});

