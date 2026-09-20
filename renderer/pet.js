import { drawMascot } from "./mascot.js"
const api = window.companion
const character = document.getElementById("character")
let down,
  dragging = false,
  ignored = false
function update(state) {
  document.body.dataset.mood = state.mood
  document.getElementById("floating-bubble").textContent = state.bubble
  if ("image" in state) {
    document.getElementById("floating-image").hidden = !state.image
    document.getElementById("mascot").hidden = Boolean(state.image)
    if (state.image) document.getElementById("floating-image").src = state.image
  }
  if (!document.getElementById("mascot").hidden)
    drawMascot(document.getElementById("mascot"), state.mood)
}
function run(promise) {
  promise.catch((error) => {
    document.getElementById("floating-bubble").textContent = error.message
  })
}
api.subscribe(update)
run(api.get().then(update))
document.getElementById("home").onclick = () => run(api.studio())
document.getElementById("feed").onclick = () => run(api.action("feed"))
document.getElementById("sleep").onclick = () => run(api.action("sleep"))
document.getElementById("hide").onclick = () => run(api["hide-pet"]())
character.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return
  down = { x: event.screenX, y: event.screenY }
  character.setPointerCapture(event.pointerId)
})
character.addEventListener("pointermove", (event) => {
  if (down && !dragging && Math.hypot(event.screenX - down.x, event.screenY - down.y) > 4) {
    dragging = true
    run(api.drag(true))
  }
})
function release(event) {
  if (!down) return
  if (dragging) run(api.drag(false))
  else if (event.type === "pointerup") run(api.action("pet"))
  down = null
  dragging = false
}
character.addEventListener("pointerup", release)
character.addEventListener("pointercancel", release)
character.addEventListener("lostpointercapture", release)
window.addEventListener("blur", () => {
  if (down) {
    run(api.drag(false))
    down = null
    dragging = false
  }
})
document.addEventListener("pointermove", (event) => {
  if (down) return
  const ignore = !event.target.closest(".interactive")
  if (ignore !== ignored) {
    ignored = ignore
    run(api.ignore(ignore))
  }
})
