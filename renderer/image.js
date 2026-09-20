// Conservative edge-connected color removal, not AI segmentation.
export function removeEdgeBackground(ctx, width, height, tolerance = 28) {
  const image = ctx.getImageData(0, 0, width, height),
    pixels = image.data
  const corners = [0, width - 1, (height - 1) * width, width * height - 1]
  const rgb = corners.map((i) => [...pixels.slice(i * 4, i * 4 + 3)])
  const bg = rgb[0]
  if (rgb.some((c) => Math.hypot(...c.map((v, i) => v - bg[i])) > tolerance)) return false
  const queue = new Int32Array(width * height),
    seen = new Uint8Array(width * height)
  let read = 0,
    write = 0
  function add(i) {
    if (seen[i]) return
    seen[i] = 1
    const k = i * 4
    if (
      pixels[k + 3] < 10 ||
      Math.hypot(pixels[k] - bg[0], pixels[k + 1] - bg[1], pixels[k + 2] - bg[2]) < tolerance
    )
      queue[write++] = i
  }
  for (let x = 0; x < width; x++) {
    add(x)
    add((height - 1) * width + x)
  }
  for (let y = 0; y < height; y++) {
    add(y * width)
    add(y * width + width - 1)
  }
  while (read < write) {
    const i = queue[read++],
      x = i % width
    pixels[i * 4 + 3] = 0
    if (x > 0) add(i - 1)
    if (x < width - 1) add(i + 1)
    if (i >= width) add(i - width)
    if (i < width * (height - 1)) add(i + width)
  }
  ctx.putImageData(image, 0, 0)
  return write > 0
}
export async function prepareImage(file, cutout) {
  if (
    !["image/png", "image/jpeg", "image/webp"].includes(file.type) ||
    file.size > 8 * 1024 * 1024
  ) {
    throw new Error("请选择 8 MB 以内的 PNG、JPG 或 WebP 图片。")
  }
  const bitmap = await createImageBitmap(file)
  if (bitmap.width * bitmap.height > 32000000) {
    bitmap.close()
    throw new Error("图片分辨率过大，请缩小到 3200 万像素以内。")
  }
  const ratio = Math.min(1, 1024 / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement("canvas")
  canvas.width = Math.max(1, Math.round(bitmap.width * ratio))
  canvas.height = Math.max(1, Math.round(bitmap.height * ratio))
  const ctx = canvas.getContext("2d", { willReadFrequently: true })
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  const removed = cutout && removeEdgeBackground(ctx, canvas.width, canvas.height)
  return { image: canvas.toDataURL("image/png"), cutout: Boolean(removed) }
}
