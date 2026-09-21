import { prepareImage } from "./image.js"
import { drawMascot } from "./mascot.js"
const api = window.companion
const $ = (id) => document.getElementById(id)
let state,
  toastTimer,
  historyKey = "",
  memoriesKey = "",
  importing = false
const labels = {
  calm: "链路稳定",
  happy: "状态良好",
  curious: "演练模式",
  sleepy: "低功耗",
  sad: "补给不足",
}
function toast(message) {
  $("toast").textContent = message
  $("toast").hidden = false
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    $("toast").hidden = true
  }, 6000)
}
async function perform(fn) {
  try {
    return await fn()
  } catch (error) {
    toast(error.message)
    return null
  }
}
function update(next) {
  state = { ...state, ...next }
  document.body.dataset.mood = state.mood
  $("pet-name").textContent = state.name
  $("personality-badge").textContent = state.personality
  $("bubble").textContent = state.bubble
  $("emotion-label").textContent = `● ${labels[state.mood] || labels.calm}`
  $("asset-kind").textContent = state.imageKind
  $("days").textContent =
    `部署第 ${Math.max(1, Math.floor((Date.now() - state.createdAt) / 86400000) + 1)} 天`
  $("connection").textContent = state.connected ? "AI 已配置" : "本地协议"
  $("chat-caption").textContent = state.busyChat
    ? "正在处理消息…"
    : state.connected
      ? "AI 通讯 · 密钥仅保留在当前进程"
      : "本地协议 · 接入 AI 后可进行自由对话"
  $("send").disabled = state.busyChat
  $("desktop-button").textContent = state.desktop ? "已部署 · 显示 ↗" : "部署到桌面 ↗"
  $("sleep-button").querySelector("b").textContent = state.sleeping ? "恢复" : "休整"
  $("generate").disabled = state.busyImage || importing
  $("generate").textContent = state.busyImage ? "正在生成战术外观…" : "AI 生成战术外观 ✦"
  for (const key of ["energy", "satiety", "affection"]) {
    $(key).value = state[key]
    $(key + "-value").textContent = Math.round(state[key])
  }
  if ("image" in next) {
    $("pet-image").hidden = !next.image
    $("mascot").hidden = Boolean(next.image)
    if (next.image) $("pet-image").src = next.image
  }
  if (!$("mascot").hidden) drawMascot($("mascot"), state.mood)
  const newHistoryKey = JSON.stringify(state.history)
  if (historyKey !== newHistoryKey) {
    historyKey = newHistoryKey
    $("conversation").replaceChildren()
    if (!state.history.length) {
      const empty = document.createElement("p")
      empty.className = "empty-conversation"
      const mark = document.createElement("span")
      mark.textContent = "07"
      empty.append(mark, "频道在线。", document.createElement("br"), "输入消息或记录一项行动备忘。")
      $("conversation").append(empty)
    }
    for (const item of state.history) {
      const row = document.createElement("div"),
        name = document.createElement("small"),
        content = document.createElement("p")
      row.className = `message ${item.role}`
      name.textContent =
        item.role === "user" ? "操作员" : `${state.name} · ${item.source || "本地协议"}`
      content.textContent = item.content
      row.append(name, content)
      $("conversation").append(row)
    }
    $("conversation").scrollTop = $("conversation").scrollHeight
  }
  const newMemoriesKey = JSON.stringify(state.memories)
  if (memoriesKey !== newMemoriesKey) {
    memoriesKey = newMemoriesKey
    $("memories").replaceChildren()
    if (!state.memories.length) {
      const li = document.createElement("li")
      li.textContent = "暂无档案条目。"
      $("memories").append(li)
    }
    state.memories.forEach((note, index) => {
      const li = document.createElement("li"),
        copy = document.createElement("span"),
        remove = document.createElement("button")
      copy.textContent = note
      remove.textContent = "×"
      remove.setAttribute("aria-label", `删除档案 ${index + 1}`)
      remove.addEventListener("click", () => perform(() => api.memory({ remove: index })))
      li.append(copy, remove)
      $("memories").append(li)
    })
  }
}
if (!api) {
  toast("请通过 npm start 启动桌面应用。")
  document.querySelectorAll("button,input,textarea,select").forEach((el) => {
    el.disabled = true
  })
} else {
  api.subscribe(update)
  const initial = await api.get()
  update(initial)
  $("name-input").value = state.name
  $("personality-input").value = state.personality
  document
    .querySelectorAll("[data-action]")
    .forEach((button) =>
      button.addEventListener("click", () => perform(() => api.action(button.dataset.action))),
    )
  $("pet-touch").addEventListener("click", () => perform(() => api.action("pet")))
  document.querySelectorAll("[data-tab]").forEach((button) =>
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-tab]").forEach((tab) => {
        tab.classList.toggle("active", tab === button)
        tab.setAttribute("aria-selected", String(tab === button))
        $("panel-" + tab.dataset.tab).hidden = tab !== button
      })
    }),
  )
  $("desktop-button").addEventListener("click", () =>
    perform(async () => {
      await api.desktop()
      toast("伙伴已部署到桌面。拖动可调整位置，菜单栏可重新打开行动台。")
    }),
  )
  $("chat-form").addEventListener("submit", (event) => {
    event.preventDefault()
    if (state.busyChat) return
    const message = $("message").value.trim()
    if (!message) return
    perform(async () => {
      $("send").disabled = true
      const result = await api.chat(message)
      $("message").value = ""
      if (result.warning) toast(result.warning)
    }).finally(() => {
      $("send").disabled = Boolean(state.busyChat)
    })
  })
  $("message").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault()
      $("chat-form").requestSubmit()
    }
  })
  $("clear-history").addEventListener("click", () => perform(() => api["clear-history"]()))
  $("profile-form").addEventListener("submit", (event) => {
    event.preventDefault()
    perform(async () => {
      await api.profile({
        name: $("name-input").value,
        personality: $("personality-input").value,
      })
      toast("单位配置已保存。")
    })
  })
  async function upload(file) {
    if (!file || importing) return
    importing = true
    $("generate").disabled = true
    await perform(async () => {
      const prepared = await prepareImage(file, $("cutout").checked)
      await api.import(prepared)
      toast(
        prepared.cutout
          ? "角色素材已导入，并已尝试移除边缘纯色背景。"
          : "角色素材已导入，可直接使用或继续生成战术外观。",
      )
    })
    importing = false
    $("generate").disabled = Boolean(state.busyImage)
    $("upload").value = ""
  }
  $("upload").addEventListener("change", (event) => upload(event.target.files[0]))
  for (const type of ["dragenter", "dragover"])
    $("dropzone").addEventListener(type, (event) => {
      event.preventDefault()
      $("dropzone").classList.add("dragover")
    })
  $("dropzone").addEventListener("dragleave", () => $("dropzone").classList.remove("dragover"))
  $("dropzone").addEventListener("drop", (event) => {
    event.preventDefault()
    $("dropzone").classList.remove("dragover")
    upload(event.dataTransfer.files[0])
  })
  window.addEventListener("dragover", (event) => event.preventDefault())
  window.addEventListener("drop", (event) => event.preventDefault())
  $("generate").addEventListener("click", () =>
    perform(async () => {
      const result = await api.generate()
      toast(result.message)
    }),
  )
  $("memory-form").addEventListener("submit", (event) => {
    event.preventDefault()
    perform(async () => {
      await api.memory({ note: $("memory-input").value })
      $("memory-input").value = ""
    })
  })
  $("settings-open").addEventListener("click", () => {
    $("base").value = state.ai.base
    $("chat-model").value = state.ai.chatModel
    $("image-model").value = state.ai.imageModel
    $("settings").showModal()
  })
  $("settings-close").addEventListener("click", () => $("settings").close())
  $("settings-form").addEventListener("submit", (event) => {
    event.preventDefault()
    perform(async () => {
      const result = await api.configure({
        base: $("base").value,
        key: $("key").value,
        chatModel: $("chat-model").value,
        imageModel: $("image-model").value,
      })
      $("key").value = ""
      $("settings").close()
      toast(result.message)
    })
  })
  $("disconnect").addEventListener("click", () =>
    perform(async () => {
      await api.disconnect()
      $("key").value = ""
      $("settings").close()
      toast("已切换至本地协议。")
    }),
  )
}
