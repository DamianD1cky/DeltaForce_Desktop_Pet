// The built-in companion is a procedural character, drawn locally, with actual
// expression changes. Uploaded images use their own pixels and body animation.
export function drawMascot(canvas, mood = "calm") {
  const ctx = canvas.getContext("2d")
  canvas.width = 600
  canvas.height = 600
  ctx.scale(2, 2)
  ctx.lineJoin = "round"
  ctx.clearRect(0, 0, 300, 300)
  function ellipse(x, y, rx, ry, color, rotation = 0) {
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.ellipse(x, y, rx, ry, rotation, 0, Math.PI * 2)
    ctx.fill()
  }
  function stroke(points, color, width) {
    ctx.strokeStyle = color
    ctx.lineWidth = width
    ctx.lineCap = "round"
    ctx.beginPath()
    ctx.moveTo(...points[0])
    for (const p of points.slice(1)) ctx.lineTo(...p)
    ctx.stroke()
  }
  // Curled tail and pear-shaped body.
  ctx.strokeStyle = "#d8b68d"
  ctx.lineWidth = 25
  ctx.lineCap = "round"
  ctx.beginPath()
  ctx.moveTo(196, 240)
  ctx.bezierCurveTo(260, 251, 260, 182, 233, 203)
  ctx.stroke()
  const body = ctx.createLinearGradient(100, 150, 220, 260)
  body.addColorStop(0, "#f7e4c5")
  body.addColorStop(1, "#d7b28b")
  ellipse(150, 216, 67, 60, body)
  ellipse(151, 224, 41, 44, "#f5e3c7")
  ellipse(109, 260, 29, 15, "#e7cba6", -0.1)
  ellipse(187, 260, 29, 15, "#e7cba6", 0.1)
  stroke(
    [
      [100, 257],
      [100, 263],
    ],
    "#c4a17a",
    1.4,
  )
  stroke(
    [
      [111, 258],
      [111, 264],
    ],
    "#c4a17a",
    1.4,
  )
  stroke(
    [
      [180, 258],
      [180, 264],
    ],
    "#c4a17a",
    1.4,
  )
  stroke(
    [
      [191, 257],
      [191, 263],
    ],
    "#c4a17a",
    1.4,
  )
  // Ears are rounded, not a separate generated image resource.
  ctx.fillStyle = "#dfbf96"
  ctx.beginPath()
  ctx.moveTo(77, 115)
  ctx.quadraticCurveTo(52, 24, 81, 37)
  ctx.quadraticCurveTo(124, 50, 126, 90)
  ctx.fill()
  ctx.beginPath()
  ctx.moveTo(174, 90)
  ctx.quadraticCurveTo(182, 49, 222, 37)
  ctx.quadraticCurveTo(247, 29, 224, 116)
  ctx.fill()
  ctx.fillStyle = "#c99583"
  ctx.beginPath()
  ctx.moveTo(82, 90)
  ctx.quadraticCurveTo(69, 47, 83, 51)
  ctx.lineTo(110, 88)
  ctx.fill()
  ctx.beginPath()
  ctx.moveTo(191, 87)
  ctx.lineTo(221, 51)
  ctx.quadraticCurveTo(233, 52, 218, 95)
  ctx.fill()
  const face = ctx.createRadialGradient(122, 94, 5, 153, 139, 110)
  face.addColorStop(0, "#fff2d9")
  face.addColorStop(0.65, "#efd5af")
  face.addColorStop(1, "#d6ae83")
  ellipse(151, 130, 88, 74, face)
  ellipse(100, 154, 33, 28, "#f7e5c9")
  ellipse(202, 154, 33, 28, "#f7e5c9")
  // Small tufts and forehead markings.
  stroke(
    [
      [137, 74],
      [140, 85],
    ],
    "#d7b78d",
    5,
  )
  stroke(
    [
      [151, 72],
      [152, 84],
    ],
    "#d7b78d",
    5,
  )
  stroke(
    [
      [165, 75],
      [163, 85],
    ],
    "#d7b78d",
    5,
  )
  for (const x of [115, 185]) {
    if (mood === "sleepy" || mood === "happy") {
      ctx.strokeStyle = "#5d4836"
      ctx.lineWidth = 4
      ctx.lineCap = "round"
      ctx.beginPath()
      ctx.moveTo(x - 9, 130)
      ctx.quadraticCurveTo(x, mood === "happy" ? 116 : 139, x + 9, 130)
      ctx.stroke()
    } else {
      ellipse(x, 128, mood === "curious" ? 9 : 7, mood === "sad" ? 7 : 10, "#523e2f")
      ellipse(x - 2, 124, 2.5, 3, "#fff6df")
    }
  }
  ellipse(96, 147, 14, 7, "#ddaa9280")
  ellipse(204, 147, 14, 7, "#ddaa9280")
  ellipse(145, 151, 13, 10, "#fff0d8")
  ellipse(159, 151, 13, 10, "#fff0d8")
  ctx.fillStyle = "#9d7160"
  ctx.beginPath()
  ctx.moveTo(145, 142)
  ctx.quadraticCurveTo(151, 138, 158, 142)
  ctx.lineTo(152, 149)
  ctx.closePath()
  ctx.fill()
  stroke(
    [
      [152, 149],
      [152, 154],
      [147, 158],
    ],
    "#88664e",
    1.6,
  )
  stroke(
    [
      [152, 154],
      [157, 158],
    ],
    "#88664e",
    1.6,
  )
  for (const sign of [-1, 1])
    for (let i = 0; i < 2; i++) {
      stroke(
        [
          [151 + sign * 62, 147 + i * 8],
          [151 + sign * 83, 142 + i * 14],
        ],
        "#b89a7a",
        1.4,
      )
    }
  // Signature rust scarf.
  ctx.strokeStyle = "#b36243"
  ctx.lineWidth = 16
  ctx.beginPath()
  ctx.moveTo(111, 190)
  ctx.quadraticCurveTo(153, 204, 192, 190)
  ctx.stroke()
  ctx.fillStyle = "#a95336"
  ctx.beginPath()
  ctx.moveTo(173, 196)
  ctx.lineTo(197, 205)
  ctx.lineTo(188, 233)
  ctx.lineTo(171, 224)
  ctx.closePath()
  ctx.fill()
  stroke(
    [
      [179, 208],
      [191, 212],
    ],
    "#d68c65",
    2,
  )
  stroke(
    [
      [177, 215],
      [189, 219],
    ],
    "#d68c65",
    2,
  )
  ellipse(102, 220, 17, 30, "#ecd0a9", -0.3)
  ellipse(202, 220, 17, 30, "#e0bc93", 0.3)
}
