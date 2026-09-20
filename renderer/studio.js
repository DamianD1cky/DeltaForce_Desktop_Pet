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
  calm: "安心陪伴",
  happy: "开心冒泡",
  curious: "好奇张望",
  sleepy: "困困的",
  sad: "有点饿了",
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
    `相遇第 ${Math.max(1, Math.floor((Date.now() - state.createdAt) / 86400000) + 1)} 天`
  $("connection").textContent = state.connected ? "AI 已配置" : "本地互动"
  $("chat-caption").textContent = state.busyChat
    ? "正在想怎么回应你…"
    : state.connected
      ? "AI 对话 · 密钥仅保留在本次会话"
      : "本地回应 · 连接 AI 后可自由聊天"
  $("send").disabled = state.busyChat
  $("desktop-button").textContent = state.desktop ? "已在桌面 · 显示 ↗" : "放到桌面 ↗"
  $("sleep-button").querySelector("b").textContent = state.sleeping ? "叫醒它" : "打个盹"
  $("generate").disabled = state.busyImage || importing
  $("generate").textContent = state.busyImage ? "正在生成，请稍候…" : "AI 转化为绒毛伙伴 ✧"
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
      mark.textContent = "“"
      empty.append(
        mark,
        "不一定要有重要的事。",
        document.createElement("br"),
        "今天的云很好看，也可以告诉我。",
      )
      $("conversation").append(empty)
    }
    for (const item of state.history) {
      const row = document.createElement("div"),
        name = document.createElement("small"),
        content = document.createElement("p")
      row.className = `message ${item.role}`
      name.textContent =
        item.role === "user" ? "你" : `${state.name} · ${item.source || "本地互动"}`
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
      li.textContent = "还没有记忆。从你喜欢的东西说起吧。"
      $("memories").append(li)
    }
    state.memories.forEach((note, index) => {
      const li = document.createElement("li"),
        copy = document.createElement("span"),
        remove = document.createElement("button")
      copy.textContent = note
      remove.textContent = "×"
      remove.setAttribute("aria-label", `删除记忆 ${index + 1}`)
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
      toast("它已经到桌面啦。拖动它可移动位置，菜单栏可找回小窝。")
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
      await api.profile({ name: $("name-input").value, personality: $("personality-input").value })
      toast("名字和性格已保存。")
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
          ? "图片已导入，已尝试去掉边缘纯色背景。"
          : "图片已导入，可以互动，也可以继续 AI 转化。",
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
      toast("已切换至本地互动。")
    }),
  )
}
