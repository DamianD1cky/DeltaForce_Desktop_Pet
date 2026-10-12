// Complete native pixel frames, selected by the main process's shared clock.
// The anatomical right-arm device is never mirrored.
export function createSpritePlayer(canvas, reportError) {
  const ctx = canvas.getContext("2d")
  const media = matchMedia("(prefers-reduced-motion: reduce)")
  let state,
    manifest,
    timer,
    lastKey = "",
    disposed = false
  const images = new Map()
  const base = new URL("../asset/sprites/redwolf-gilded-rose/", import.meta.url)

  function schedule(delay) {
    clearTimeout(timer)
    if (!disposed && !document.hidden && !canvas.hidden) {
      // An early timer must not postpone the next frame by another 16ms.
      timer = setTimeout(render, Math.max(1, delay))
    }
  }
  function render() {
    clearTimeout(timer)
    if (disposed || !manifest || canvas.hidden || document.hidden) return
    const now = Date.now()
    const ending = state.animation ? state.animation.startedAt + state.animation.durationMs : 0
    const active = state.animation && now < ending ? state.animation : null
    const name = active?.name || (state.sleeping ? "sleep" : "idle")
    const clip = manifest.clips[name]
    if (!clip) return
    const reduced = media.matches || active?.reducedMotion
    // Loops restart where the previous clip ended; every action ends on loop frame 0.
    const epoch = state.animation ? ending : state.loopEpoch || 0
    const elapsed = active
      ? Math.max(0, now - active.startedAt)
      : (((now - epoch) % clip.durationMs) + clip.durationMs) % clip.durationMs
    let frame = 0,
      end = clip.durations[0]
    while (frame < clip.frameCount - 1 && elapsed >= end) end += clip.durations[++frame]
    if (reduced) frame = active ? clip.keyframe : 0
    const image = images.get(name)
    const key = `${name}:${frame}`
    if (image?.complete && image.naturalWidth && key !== lastKey) {
      const [x, y, w, h] = clip.cell
      const cell = clip.cells[frame]
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.imageSmoothingEnabled = false
      ctx.drawImage(
        image,
        (cell % clip.columns) * w,
        Math.floor(cell / clip.columns) * h,
        w,
        h,
        x,
        y,
        w,
        h,
      )
      canvas.dataset.clip = name
      canvas.dataset.frame = String(frame)
      canvas.dataset.actionId = String(active?.id || 0)
      canvas.dataset.ready = "true"
      lastKey = key
    }
    if (reduced) {
      if (active) schedule(ending - now + 1)
    } else schedule(active ? Math.min(end - elapsed, ending - now + 1) : end - elapsed)
  }
  function wake() {
    lastKey = ""
    render()
  }
  document.addEventListener("visibilitychange", wake)
  media.addEventListener("change", wake)
  return {
    update(next) {
      state = next
      if (!manifest) {
        manifest = next.sprites
        canvas.width = manifest.frameWidth
        canvas.height = manifest.frameHeight
        for (const [name, clip] of Object.entries(manifest.clips)) {
          const image = new Image()
          images.set(name, image)
          image.onload = wake
          image.onerror = () => reportError(`红狼动作资源加载失败：${clip.label}`)
          image.src = new URL(clip.file, base).href
        }
      }
      // An identical frame can still belong to a newly received action.
      lastKey = ""
      render()
    },
    dispose() {
      disposed = true
      clearTimeout(timer)
      document.removeEventListener("visibilitychange", wake)
      media.removeEventListener("change", wake)
      for (const image of images.values()) image.onload = image.onerror = null
    },
  }
}

export function updateSkillControls(state) {
  const unavailable = state.hasImage || state.sleeping || Boolean(state.animation)
  document.querySelectorAll("[data-skill]").forEach((button) => {
    button.disabled = unavailable
    button.setAttribute("aria-pressed", String(state.animation?.name === button.dataset.skill))
  })
  const status = document.getElementById("skill-status")
  if (status)
    status.textContent = state.hasImage
      ? "恢复红狼后可使用专属动作"
      : state.animation
        ? `正在${state.sprites.clips[state.animation.name].label}…`
        : state.sleeping
          ? "休息中 · 叫醒后可使用动作"
          : "专属动作就绪"
}

export function bindSkillControls(api, run) {
  document.querySelectorAll("[data-skill]").forEach((button) => {
    button.addEventListener("click", () =>
      run(
        api.skill({
          name: button.dataset.skill,
          reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
        }),
      ),
    )
  })
}
