// D-07 is an original local Canvas character. Uploaded images keep their own
// pixels and use the same body-level motion as this built-in unit.
export function drawMascot(canvas, mood = "calm") {
  const ctx = canvas.getContext("2d")
  canvas.width = 600
  canvas.height = 600
  ctx.scale(2, 2)
  ctx.lineJoin = "round"
  ctx.lineCap = "round"
  ctx.clearRect(0, 0, 300, 300)

  const signal = mood === "sad" ? "#ffb547" : mood === "sleepy" ? "#7f9185" : "#b8ff3d"
  const armorDark = "#171c1a"
  const armorLight = "#59645b"

  function ellipse(x, y, rx, ry, color, rotation = 0) {
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.ellipse(x, y, rx, ry, rotation, 0, Math.PI * 2)
    ctx.fill()
  }

  function stroke(points, color, width) {
    ctx.strokeStyle = color
    ctx.lineWidth = width
    ctx.beginPath()
    ctx.moveTo(...points[0])
    for (const point of points.slice(1)) ctx.lineTo(...point)
    ctx.stroke()
  }

  function panel(x, y, width, height, radius, color) {
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.roundRect(x, y, width, height, radius)
    ctx.fill()
  }

  // Antenna and compact field pack.
  stroke(
    [
      [204, 86],
      [218, 50],
    ],
    armorLight,
    5,
  )
  ellipse(219, 47, 7, 7, signal)
  ellipse(219, 47, 12, 12, `${signal}24`)
  panel(64, 151, 34, 88, 10, armorDark)
  panel(68, 160, 27, 28, 5, "#465048")
  stroke(
    [
      [74, 198],
      [89, 198],
    ],
    signal,
    3,
  )

  // Boots and articulated legs.
  panel(99, 224, 38, 45, 13, armorDark)
  panel(164, 224, 38, 45, 13, armorDark)
  panel(91, 254, 51, 22, 9, "#222825")
  panel(159, 254, 51, 22, 9, "#222825")
  stroke(
    [
      [101, 264],
      [132, 264],
    ],
    armorLight,
    2,
  )
  stroke(
    [
      [169, 264],
      [200, 264],
    ],
    armorLight,
    2,
  )

  // Torso shell, shoulder plates and utility belt.
  const torso = ctx.createLinearGradient(96, 142, 206, 248)
  torso.addColorStop(0, "#4b564e")
  torso.addColorStop(0.55, "#303833")
  torso.addColorStop(1, "#202623")
  panel(91, 142, 118, 108, 31, torso)
  panel(74, 151, 38, 64, 17, "#3d4740")
  panel(190, 151, 38, 64, 17, "#3d4740")
  panel(80, 203, 32, 48, 13, armorDark)
  panel(190, 203, 32, 48, 13, armorDark)
  panel(103, 207, 96, 19, 6, armorDark)
  for (const x of [112, 134, 156, 178]) panel(x, 211, 14, 11, 3, "#566158")

  // Chest identifier and status module.
  panel(110, 157, 80, 44, 9, "#1c2220")
  ctx.fillStyle = signal
  ctx.beginPath()
  ctx.moveTo(126, 190)
  ctx.lineTo(143, 166)
  ctx.lineTo(151, 190)
  ctx.lineTo(143, 186)
  ctx.lineTo(140, 178)
  ctx.lineTo(133, 188)
  ctx.closePath()
  ctx.fill()
  panel(158, 167, 21, 4, 2, "#758078")
  panel(158, 176, 16, 4, 2, signal)
  panel(158, 185, 11, 4, 2, "#758078")

  // Helmet shell and side audio modules.
  const helmet = ctx.createLinearGradient(78, 52, 220, 143)
  helmet.addColorStop(0, "#626e64")
  helmet.addColorStop(0.45, "#39423c")
  helmet.addColorStop(1, "#202623")
  ctx.fillStyle = helmet
  ctx.beginPath()
  ctx.moveTo(85, 112)
  ctx.quadraticCurveTo(85, 50, 150, 40)
  ctx.quadraticCurveTo(215, 49, 217, 112)
  ctx.quadraticCurveTo(208, 157, 151, 164)
  ctx.quadraticCurveTo(94, 157, 85, 112)
  ctx.fill()
  panel(69, 94, 31, 49, 12, armorDark)
  panel(202, 94, 31, 49, 12, armorDark)
  panel(75, 104, 18, 27, 6, armorLight)
  panel(209, 104, 18, 27, 6, armorLight)
  stroke(
    [
      [96, 72],
      [122, 56],
      [180, 56],
      [205, 72],
    ],
    "#78847a",
    3,
  )
  panel(140, 48, 22, 6, 3, signal)

  // Visor and expression display.
  const visor = ctx.createLinearGradient(101, 88, 200, 132)
  visor.addColorStop(0, "#0b0f0e")
  visor.addColorStop(1, "#19231d")
  panel(99, 83, 104, 57, 18, visor)
  stroke(
    [
      [112, 132],
      [190, 132],
    ],
    "#3d4a41",
    2,
  )

  for (const x of [126, 176]) {
    if (mood === "happy") {
      ctx.strokeStyle = signal
      ctx.lineWidth = 6
      ctx.beginPath()
      ctx.moveTo(x - 12, 112)
      ctx.quadraticCurveTo(x, 98, x + 12, 112)
      ctx.stroke()
    } else if (mood === "sleepy") {
      stroke(
        [
          [x - 11, 111],
          [x + 11, 111],
        ],
        signal,
        5,
      )
    } else if (mood === "sad") {
      stroke(
        [
          [x - 10, x === 126 ? 105 : 113],
          [x + 10, x === 126 ? 113 : 105],
        ],
        signal,
        5,
      )
    } else {
      ellipse(x, 108, mood === "curious" && x === 176 ? 9 : 7, 9, signal)
      ellipse(x - 2, 105, 2, 3, "#ecffcf")
    }
  }

  // Chin guard, fasteners and restrained wear marks.
  panel(122, 145, 58, 13, 6, "#202623")
  ellipse(91, 118, 3, 3, signal)
  ellipse(211, 118, 3, 3, signal)
  stroke(
    [
      [117, 67],
      [131, 64],
    ],
    "#8c978e",
    2,
  )
  stroke(
    [
      [182, 71],
      [193, 77],
    ],
    "#68746a",
    2,
  )
}
