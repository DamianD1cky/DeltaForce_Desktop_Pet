import { _electron as electron } from "playwright"
import assert from "node:assert/strict"
import { mkdtemp, readFile, mkdir, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import path from "node:path"
import { fileURLToPath } from "node:url"
import http from "node:http"

const root = fileURLToPath(new URL("../", import.meta.url))
const sprites = JSON.parse(
  await readFile(path.join(root, "asset/sprites/redwolf-gilded-rose/animations.json"), "utf8"),
)
const results = path.join(root, "test-results")
await mkdir(results, { recursive: true })
const dataDir = await mkdtemp(path.join(tmpdir(), "delta-companion-e2e-"))
let image
const fixturePath = path.join(results, "upload-fixture.png")
const requests = []
let mode = "ok"
const server = http.createServer(async (req, res) => {
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  const body = Buffer.concat(chunks).toString()
  requests.push({ url: req.url, body })
  res.setHeader("Content-Type", "application/json")
  if (mode === "fail") {
    res.writeHead(503)
    res.end('{"error":"fixture unavailable"}')
    return
  }
  if (req.url === "/v1/images/edits") {
    res.end(JSON.stringify({ data: [{ b64_json: image.toString("base64") }] }))
  } else {
    res.end(
      JSON.stringify({
        choices: [
          {
            message: {
              content:
                mode === "malformed"
                  ? "not-json"
                  : JSON.stringify({
                      reply: "我记得你喜欢雨天，我们一起听雨吧。",
                      emotion: "happy",
                    }),
            },
          },
        ],
      }),
    )
  }
})
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve))
const base = `http://127.0.0.1:${server.address().port}/v1`
const env = {
  ...process.env,
  PET_DATA_DIR: dataDir,
  PET_AI_KEY: "",
  OPENAI_API_KEY: "",
}
delete env.ELECTRON_RUN_AS_NODE
const checks = [],
  errors = []
let app
async function launch() {
  const instance = await electron.launch({ args: [root], env })
  const page = await instance.firstWindow()
  page.on("pageerror", (error) => errors.push(error.message))
  await page.locator("#pet-name").waitFor()
  await page.waitForFunction(() => document.querySelector("#energy-value").textContent !== "")
  await page.waitForFunction(
    () =>
      document.querySelector("#mascot").dataset.ready === "true" ||
      !document.querySelector("#pet-image").hidden,
  )
  return { instance, page }
}
async function configure(page) {
  await page.locator("#settings-open").click()
  await page.locator("#base").fill(base)
  await page.locator("#key").fill("e2e-not-a-real-key")
  await page.locator("#settings-form button[type=submit]").click()
  await page.waitForFunction(() => !document.querySelector("#settings").open)
}
async function send(page, message) {
  const count = await page.locator(".message.assistant").count()
  await page.locator("#message").fill(message)
  await page.locator("#send").click()
  await page.waitForFunction(
    (n) => document.querySelectorAll(".message.assistant").length > n,
    count,
  )
}
try {
  let launched = await launch()
  app = launched.instance
  let page = launched.page
  assert(
    await page
      .locator("#desktop-button")
      .evaluate((el) => el.getBoundingClientRect().bottom <= window.innerHeight),
  )
  await page.screenshot({ path: path.join(results, "studio.png") })
  const characterData = await page.locator("#mascot").evaluate((el) => el.toDataURL("image/png"))
  image = Buffer.from(characterData.split(",")[1], "base64")
  assert(image.length > 1000)
  await writeFile(fixturePath, image)
  assert.equal(await page.locator("#pet-name").textContent(), "红狼")
  assert.equal(
    await page.locator("#mascot").evaluate((el) => getComputedStyle(el).imageRendering),
    "pixelated",
  )
  assert.equal(await page.locator("#mascot").evaluate((el) => el.getBoundingClientRect().width), 240)
  checks.push("native Electron launch and bundled Red Wolf pixel atlas")
  const before = Number(await page.locator("#affection-value").textContent())
  await page.locator('[data-action="pet"]').click()
  await page.waitForFunction(
    (n) => Number(document.querySelector("#affection-value").textContent) > n,
    before,
  )
  await page.locator('[data-action="feed"]').click()
  await page.locator('[data-action="play"]').click()
  await page.locator('[data-action="sleep"]').click()
  await page.waitForFunction(() => document.body.dataset.mood === "sleepy")
  await page.locator('[data-action="sleep"]').click()
  checks.push("pet / feed / play / sleep / wake actions")
  await send(page, "今天有点累")
  assert.match(await page.locator(".message.assistant").last().textContent(), /本地协议/)
  checks.push("offline protocol clearly labelled")
  await page.locator('[data-tab="memory"]').click()
  await page.locator("#memory-input").fill("我喜欢雨天")
  await page.locator("#memory-form button").click()
  await page.getByText("我喜欢雨天", { exact: true }).waitFor()
  checks.push("explicit persistent memory")
  await page.locator('[data-tab="create"]').click()
  await page.locator("#name-input").fill("团子")
  await page.locator("#personality-input").selectOption("敏锐")
  await page.locator("#profile-form button").click()
  await page.locator("#upload").setInputFiles(fixturePath)
  await page.waitForFunction(
    () => document.querySelector("#asset-kind").textContent !== "红狼 · 蚀金玫瑰",
  )
  assert(await page.locator('[data-skill="slide"]').isDisabled())
  checks.push("PNG upload, processing, profile edit")
  await configure(page)
  await page.locator("#settings-open").click()
  await page.locator("#base").fill("https://example.com/v1")
  await page.locator("#settings-form button[type=submit]").click()
  await page.waitForFunction(() =>
    document.querySelector("#toast").textContent.includes("重新填写密钥"),
  )
  await page.locator("#settings-close").click()
  checks.push("provider change cannot silently reuse existing key")
  await page.locator("#generate").click()
  await page.waitForFunction(() => document.querySelector("#asset-kind").textContent === "AI 转化")
  const edit = requests.find((req) => req.url === "/v1/images/edits")
  assert(
    edit &&
      edit.body.includes('name="image"') &&
      edit.body.includes("transparent") &&
      edit.body.includes("gpt-image-1.5"),
  )
  checks.push("Images Edits multipart contract (mock provider)")
  mode = "fail"
  await page.locator("#generate").click()
  await page.waitForFunction(() =>
    document.querySelector("#toast").textContent.includes("HTTP 503"),
  )
  assert.equal(await page.locator("#asset-kind").textContent(), "AI 转化")
  checks.push("image failure keeps existing asset")
  mode = "ok"
  await page.locator('[data-tab="chat"]').click()
  await send(page, "你还记得我的喜好吗")
  assert.match(await page.locator(".message.assistant").last().textContent(), /AI/)
  const chatRequest = JSON.parse(requests.find((req) => req.url === "/v1/chat/completions").body)
  assert(chatRequest.messages[0].content.includes("我喜欢雨天"))
  checks.push("AI chat schema and memory injection (mock provider)")
  mode = "malformed"
  await send(page, "再说一句吧")
  assert.match(await page.locator(".message.assistant").last().textContent(), /本地回退/)
  checks.push("malformed AI JSON falls back explicitly")
  mode = "fail"
  await send(page, "服务器出错了")
  assert.match(await page.locator(".message.assistant").last().textContent(), /本地回退/)
  checks.push("HTTP failure falls back explicitly")
  const windowPromise = app.waitForEvent("window")
  await page.locator("#desktop-button").click()
  const pet = await windowPromise
  pet.on("pageerror", (error) => errors.push(error.message))
  await pet.locator("#floating-image").waitFor()
  const desktop = await app.evaluate(({ BrowserWindow }) => {
    const win = BrowserWindow.getAllWindows().find(
      (w) => w.getTitle() === "Delta Companion 桌面伙伴",
    )
    return {
      top: win.isAlwaysOnTop(),
      size: win.getSize(),
      background: win.getBackgroundColor(),
      isolation: win.webContents.getLastWebPreferences().contextIsolation,
      node: win.webContents.getLastWebPreferences().nodeIntegration,
    }
  })
  assert(desktop.top && desktop.isolation && !desktop.node)
  assert.deepEqual(desktop.size, [360, 440])
  await pet.locator("#feed").click()
  await page.waitForFunction(() => document.querySelector("#bubble").textContent.includes("补给"))
  const petPng = await pet.screenshot({
    path: path.join(results, "desktop-pet.png"),
    omitBackground: true,
  })
  const cornerAlpha = await app.evaluate(({ nativeImage }, encoded) => {
    const image = nativeImage.createFromBuffer(Buffer.from(encoded, "base64"))
    return image.toBitmap()[3]
  }, petPng.toString("base64"))
  assert.equal(cornerAlpha, 0)
  checks.push("desktop window screenshot contains a fully transparent corner")
  // Exercise real atlas playback and shared main-process skill state in both windows.
  await page.locator('[data-tab="create"]').click()
  await page.locator("#restore-redwolf").click()
  await pet.locator("#mascot").waitFor()
  await pet.waitForFunction(() => document.querySelector("#mascot").dataset.ready === "true")
  assert.equal(await pet.locator("#mascot").evaluate((el) => el.getBoundingClientRect().width), 240)
  assert.equal(await pet.locator("#character").evaluate((el) => el.getBoundingClientRect().width), 240)
  for (const clip of Object.values(sprites.clips)) {
    assert(clip.frameCount >= 36)
    assert.equal(clip.durations.length, clip.frameCount)
    assert(clip.durations.every((duration) => duration === 40))
    assert.equal(clip.durationMs, clip.durations.reduce((a, b) => a + b, 0))
  }
  checks.push("240px character in both windows; all five clips have 25fps timelines")
  await page.locator('[data-tab="chat"]').click()
  // Place the pet away from the edge to verify actual slide displacement.
  const slideOrigin = await app.evaluate(({ BrowserWindow, screen }) => {
    const win = BrowserWindow.getAllWindows().find(
      (w) => w.getTitle() === "Delta Companion 桌面伙伴",
    )
    const area = screen.getPrimaryDisplay().workArea
    win.setPosition(area.x + 40, area.y + area.height - 460)
    return win.getPosition()
  })
  for (const name of ["slide", "rose", "cannon"]) {
    await pet.locator(`[data-skill="${name}"]`).click()
    await page.waitForFunction(
      (name) => document.querySelector("#mascot").dataset.clip === name,
      name,
    )
    await pet.waitForFunction(({ name, keyframe }) => {
      const c = document.querySelector("#mascot")
      return c.dataset.clip === name && Number(c.dataset.frame) >= keyframe
    }, { name, keyframe: sprites.clips[name].keyframe })
    const sync = await Promise.all(
      [page, pet].map((p) =>
        p.locator("#mascot").evaluate((el) => ({
          id: el.dataset.actionId,
          clip: el.dataset.clip,
          frame: Number(el.dataset.frame),
          pixels: el.toDataURL(),
        })),
      ),
    )
    assert.equal(sync[0].id, sync[1].id)
    assert.equal(sync[0].clip, name)
    assert(Math.abs(sync[0].frame - sync[1].frame) <= 1)
    assert.notEqual(sync[0].pixels, characterData)
    await pet.screenshot({
      path: path.join(results, `redwolf-${name}.png`),
      omitBackground: true,
    })
    assert(await page.locator('[data-skill="cannon"]').isDisabled())
    // Main-process rejection is also required, even when UI guards are bypassed.
    const rejected = await page.evaluate(async () => {
      try {
        await window.companion.skill({ name: "cannon" })
        return false
      } catch {
        return true
      }
    })
    assert(rejected)
    await pet.waitForFunction(() => document.querySelector("#mascot").dataset.clip === "idle")
  }
  const slideEnd = await app.evaluate(({ BrowserWindow }) =>
    BrowserWindow.getAllWindows()
      .find((w) => w.getTitle() === "Delta Companion 桌面伙伴")
      .getPosition(),
  )
  assert.equal(slideEnd[0] - slideOrigin[0], 150)
  assert.equal(slideEnd[1], slideOrigin[1])
  checks.push(
    "slide travels 150px; rose crush and right-arm cannon animate and synchronize across windows",
  )

  await page.locator('[data-skill="rose"]').click()
  await pet.locator("#sleep").click()
  await pet.waitForFunction(() => document.querySelector("#mascot").dataset.clip === "sleep")
  assert(await page.locator('[data-skill="rose"]').isDisabled())
  assert.equal(await page.evaluate(async () => (await window.companion.get()).animation), null)
  await pet.locator("#sleep").click()
  // Reduced motion keeps one representative frame and does not move the window.
  await page.emulateMedia({ reducedMotion: "reduce" })
  await page.locator('[data-skill="slide"]').click()
  await page.waitForFunction(() => document.querySelector("#mascot").dataset.clip === "slide")
  assert.equal(
    await page.locator("#mascot").getAttribute("data-frame"),
    String(sprites.clips.slide.keyframe),
  )
  await pet.waitForFunction(() => document.querySelector("#mascot").dataset.clip === "idle")
  const still = await app.evaluate(({ BrowserWindow }) =>
    BrowserWindow.getAllWindows()
      .find((w) => w.getTitle() === "Delta Companion 桌面伙伴")
      .getPosition(),
  )
  assert.deepEqual(still, slideEnd)
  await page.emulateMedia({ reducedMotion: "no-preference" })
  checks.push("sleep interrupts actions; reduced motion shows a keyframe without sliding")

  // At the right edge, never teleport backwards to create a runway.
  const edge = await app.evaluate(({ BrowserWindow, screen }) => {
    const win = BrowserWindow.getAllWindows().find(
      (w) => w.getTitle() === "Delta Companion 桌面伙伴",
    )
    const area = screen.getDisplayMatching(win.getBounds()).workArea
    win.setPosition(area.x + area.width - win.getSize()[0], win.getPosition()[1])
    return win.getPosition()
  })
  await pet.locator('[data-skill="slide"]').click()
  await pet.waitForFunction(() => document.querySelector("#mascot").dataset.clip === "slide")
  await pet.waitForFunction(() => document.querySelector("#mascot").dataset.clip === "idle")
  assert.deepEqual(
    await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()
        .find((w) => w.getTitle() === "Delta Companion 桌面伙伴")
        .getPosition(),
    ),
    edge,
  )
  checks.push("slide is clamped at the display edge without teleporting")

  await page.locator('[data-skill="cannon"]').click()
  await pet.locator("#hide").click()
  await page.waitForFunction(() =>
    document.querySelector("#desktop-button").textContent.includes("部署到桌面"),
  )
  checks.push("transparent always-on-top native window, cross-window sync, hide")
  assert.equal(await page.evaluate(async () => (await window.companion.get()).animation), null)
  // Importing during an action cancels playback; saved custom images still restore.
  await page.locator('[data-skill="rose"]').click()
  await page.locator('[data-tab="create"]').click()
  await page.locator("#name-input").fill("团子")
  await page.locator("#profile-form button").click()
  await page.locator("#upload").setInputFiles(fixturePath)
  await page.waitForFunction(() => !document.querySelector("#pet-image").hidden)
  assert.equal(await page.evaluate(async () => (await window.companion.get()).animation), null)
  checks.push("hide and image import cancel active skills; restoring Red Wolf re-enables skills")
  await app.close()
  app = null
  launched = await launch()
  app = launched.instance
  page = launched.page
  assert.equal(await page.locator("#pet-name").textContent(), "团子")
  assert.equal(await page.locator("#connection").textContent(), "本地协议")
  assert((await page.locator(".message").count()) >= 6)
  await page.locator('[data-tab="memory"]').click()
  assert.match(await page.locator("#memories").textContent(), /我喜欢雨天/)
  await page.getByRole("button", { name: "删除档案 1" }).click()
  await page.waitForFunction(() =>
    document.querySelector("#memories").textContent.includes("暂无档案"),
  )
  const saved = await readFile(path.join(dataDir, "companion.json"), "utf8")
  assert(!saved.includes("e2e-not-a-real-key"))
  checks.push(
    "restart restores profile, image, messages, memory; key never persisted; memory deletion",
  )
  assert.deepEqual(errors, [])
  checks.push("no renderer runtime errors")
  const report = {
    platform: process.platform,
    arch: process.arch,
    at: new Date().toISOString(),
    checks,
    nativeWindow: desktop,
    liveAI: false,
    windowsRuntimeTested: process.platform === "win32",
  }
  await writeFile(path.join(results, "smoke.json"), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} finally {
  if (app) await app.close()
  server.close()
}
