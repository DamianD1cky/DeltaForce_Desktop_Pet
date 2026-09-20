import { _electron as electron } from "playwright"
import assert from "node:assert/strict"
import { mkdtemp, readFile, mkdir, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import path from "node:path"
import { fileURLToPath } from "node:url"
import http from "node:http"

const root = fileURLToPath(new URL("../", import.meta.url))
const results = path.join(root, "test-results")
await mkdir(results, { recursive: true })
const dataDir = await mkdtemp(path.join(tmpdir(), "softspot-e2e-"))
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
const env = { ...process.env, PET_DATA_DIR: dataDir, PET_AI_KEY: "", OPENAI_API_KEY: "" }
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
  checks.push("native Electron launch and procedural mascot")
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
  assert.match(await page.locator(".message.assistant").last().textContent(), /本地互动/)
  checks.push("offline chat clearly labelled")
  await page.locator('[data-tab="memory"]').click()
  await page.locator("#memory-input").fill("我喜欢雨天")
  await page.locator("#memory-form button").click()
  await page.getByText("我喜欢雨天", { exact: true }).waitFor()
  checks.push("explicit persistent memory")
  await page.locator('[data-tab="create"]').click()
  await page.locator("#name-input").fill("团子")
  await page.locator("#personality-input").selectOption("活泼")
  await page.locator("#profile-form button").click()
  await page.locator("#upload").setInputFiles(fixturePath)
  await page.waitForFunction(() => document.querySelector("#asset-kind").textContent !== "内置角色")
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
    const win = BrowserWindow.getAllWindows().find((w) => w.getTitle() === "Softspot 桌宠")
    return {
      top: win.isAlwaysOnTop(),
      size: win.getSize(),
      background: win.getBackgroundColor(),
      isolation: win.webContents.getLastWebPreferences().contextIsolation,
      node: win.webContents.getLastWebPreferences().nodeIntegration,
    }
  })
  assert(desktop.top && desktop.isolation && !desktop.node)
  assert.deepEqual(desktop.size, [300, 350])
  await pet.locator("#feed").click()
  await page.waitForFunction(
    () =>
      document.querySelector("#bubble").textContent.includes("点心") ||
      document.querySelector("#bubble").textContent.includes("啊呜"),
  )
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
  await pet.locator("#hide").click()
  await page.waitForFunction(() =>
    document.querySelector("#desktop-button").textContent.includes("放到桌面"),
  )
  checks.push("transparent always-on-top native window, cross-window sync, hide")
  await app.close()
  app = null
  launched = await launch()
  app = launched.instance
  page = launched.page
  assert.equal(await page.locator("#pet-name").textContent(), "团子")
  assert.equal(await page.locator("#connection").textContent(), "本地互动")
  assert((await page.locator(".message").count()) >= 6)
  await page.locator('[data-tab="memory"]').click()
  assert.match(await page.locator("#memories").textContent(), /我喜欢雨天/)
  await page.getByRole("button", { name: "删除记忆 1" }).click()
  await page.waitForFunction(() =>
    document.querySelector("#memories").textContent.includes("还没有记忆"),
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
