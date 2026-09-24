import { expect, test, type Page } from "@playwright/test";

const user = { id: "qa", display_name: "QA", email: "qa@example.com", role: "advertiser", age: 25, gender: "unspecified" };
const video = { id: "v", title: "Anuncio de prueba", category: "ciencia", description: "", tags: [], audio_id: "a", duration_ms: 10000,
  creator_id: "creator", creator_name: "Marca", width: 1080, height: 1920, poster_seed: "qa", media_url: null, media_path: null, play_count: 0,
  comment_count: 0, share_count: 0, followee: false };

async function signedIn(page: Page) {
  await page.addInitScript((u) => { localStorage.setItem("veta.token", "qa-token"); localStorage.setItem("veta.user", JSON.stringify(u)); }, user);
  await page.route("**/api/me/profile", (route) => route.fulfill({ json: {user, videos:[video], clip_count:1, follow_count:0} }));
}

test("editar género conserva la selección y permite retirarla", async ({page}) => {
  await signedIn(page);
  let submitted = "";
  await page.route("**/api/auth/me", (route) => { submitted = route.request().postDataJSON().gender;
    return route.fulfill({json:{...user, gender:submitted}}); });
  await page.goto("/yo");
  await page.getByRole("combobox", {name:/Género/}).selectOption("woman");
  await page.getByRole("button", {name:"Guardar perfil"}).click();
  await expect(page.getByRole("status")).toHaveText("Perfil actualizado");
  expect(submitted).toBe("woman");
  await page.getByRole("combobox", {name:/Género/}).selectOption("unspecified");
  await page.getByRole("button", {name:"Guardar perfil"}).click();
  await expect.poll(() => submitted).toBe("unspecified");
});

test("crear campaña segmentada y consultar resultados", async ({page}) => {
  await signedIn(page);
  const rows: object[] = [];
  let campaign: Record<string, unknown> = {};
  await page.route("**/api/campaigns", (route) => {
    if (route.request().method() === "POST") {
      campaign = route.request().postDataJSON(); rows.push({...campaign, id:"c", status:"active", spent_today_cents:0});
      return route.fulfill({status:201, json:rows[0]});
    }
    return route.fulfill({json:rows});
  });
  await page.route("**/api/campaigns/c/metrics?*", (route) => route.fulfill({json:{impressions:10, users:8, clicks:2, ctr:.2,
    spend_cents:180, cpc_cents:90, remaining_cents:3820, delivery:"eligible_subject_to_targeting", genders:[]}}));
  await page.goto("/anuncios");
  await page.getByLabel("Nombre", {exact:true}).fill("Campaña medible");
  await page.getByRole("combobox", {name:"Video",exact:true}).selectOption("v");
  await page.getByLabel("Enlace de destino").fill("https://example.com/oferta");
  await page.getByRole("checkbox", {name:"Mujer",exact:true}).check();
  await page.getByRole("button", {name:"Crear campaña"}).click();
  await expect(page.getByRole("heading", {name:"Campaña medible"})).toBeVisible();
  expect(campaign.targeting_genders).toEqual(["woman"]);
  expect(campaign.landing_url).toBe("https://example.com/oferta");
  await expect(page.getByText("20.0%", {exact:true})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path:`../../output/playwright/campaigns-${test.info().project.name}.png`, fullPage:true});
});

test("anuncio enlaza clic e impresión a la misma exposición", async ({page, context}) => {
  await signedIn(page);
  let exposure = "", click = "";
  const events: {exposure_id:string; event_type:string}[] = [];
  await page.route("**/api/feed?*", (route) => route.fulfill({json:{items:[{kind:"ad", video_id:"v", campaign_id:"c", creative_id:"cr",
    decision_id:"decision", landing_url:"https://example.com/oferta", source:"auction", position:3, scores:{}, reasons:[], video}], trace:{}, latency_ms:1, new_user:true}}));
  await page.route("**/api/exposures", (route) => { exposure = route.request().postDataJSON().exposure_id; return route.fulfill({json:{exposure_id:exposure}}); });
  await page.route("**/api/events", (route) => { events.push(...route.request().postDataJSON().events); return route.fulfill({json:{accepted:1}}); });
  await page.route("**/api/campaigns/click", (route) => {click = route.request().postDataJSON().exposure_id; return route.fulfill({json:{landing_url:"https://example.com/oferta", charged_cents:90}});});
  await context.route("https://example.com/oferta", (route) => route.fulfill({contentType:"text/html", body:"<h1>Destino de prueba</h1>"}));
  await page.goto("/");
  await expect(page.getByRole("button", {name:"Visitar sitio"})).toBeVisible();
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", {name:"Visitar sitio"}).click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", {name:"Destino de prueba"})).toBeVisible();
  expect(click).toBe(exposure); expect(exposure).not.toBe("");
  await expect.poll(() => events.filter((e) => e.event_type === "impression").length).toBe(1);
  expect(events.every((e) => e.exposure_id === exposure)).toBe(true);
});
