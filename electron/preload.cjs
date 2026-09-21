const { contextBridge, ipcRenderer } = require("electron")
const methods = [
  "get",
  "action",
  "skill",
  "restore-redwolf",
  "chat",
  "generate",
  "profile",
  "import",
  "configure",
  "disconnect",
  "memory",
  "clear-history",
  "desktop",
  "studio",
  "hide-pet",
  "ignore",
  "drag",
  "quit",
]
const api = {}
for (const method of methods)
  api[method] = async (payload) => {
    const response = await ipcRenderer.invoke(`pet:${method}`, payload)
    if (!response.ok) throw new Error(response.error)
    return response.data
  }
api.subscribe = (callback) => {
  const handler = (_event, data) => callback(data)
  ipcRenderer.on("pet:state", handler)
  return () => ipcRenderer.removeListener("pet:state", handler)
}
contextBridge.exposeInMainWorld("companion", api)
