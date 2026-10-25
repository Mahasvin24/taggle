export type Point = { x: number; y: number };
export type Pose = Point & { angle: number; w: number; h: number };
export type Alpha = { width: number; height: number; data: Uint8ClampedArray };
export function pose(
  p: {
    spawn_ms: number;
    flight_ms: number;
    lane: number;
    drift: number;
    rotation: number;
    spin: number;
    width: number;
    height: number;
  },
  time: number,
  width: number,
  height: number,
): Pose {
  const u = Math.max(0, Math.min(1, (time - p.spawn_ms) / p.flight_ms));
  const size = Math.min(184, Math.max(98, width * 0.17));
  const scale = size / Math.max(p.width, p.height);
  // Reserve space for the HUD even when a large sprite rotates onto its diagonal.
  const apex = Math.max(height * 0.23, 92 + (Math.hypot(p.width, p.height) * scale) / 2);
  return {
    x: width * (p.lane + p.drift * (u - 0.5)),
    y: height + size * 0.6 - 4 * u * (1 - u) * (height + size * 0.6 - apex),
    angle: p.rotation + (p.spin * (time - p.spawn_ms)) / 1000,
    w: p.width * scale,
    h: p.height * scale,
  };
}
export function local(point: Point, fruit: Pose): Point {
  const dx = point.x - fruit.x,
    dy = point.y - fruit.y,
    c = Math.cos(fruit.angle),
    s = Math.sin(fruit.angle);
  return { x: dx * c + dy * s, y: -dx * s + dy * c };
}
export function sweptHit(
  a: Point,
  b: Point,
  fruit: Pose,
  alpha: Alpha,
): boolean {
  const start = local(a, fruit),
    end = local(b, fruit);
  const steps = Math.ceil(
    Math.hypot(end.x - start.x, end.y - start.y) /
      Math.max(0.5, Math.min(fruit.w / alpha.width, fruit.h / alpha.height)),
  );
  for (let i = 0; i <= steps; i++) {
    const t = steps === 0 ? 0 : i / steps;
    const x = Math.floor(
      ((start.x + (end.x - start.x) * t) / fruit.w + 0.5) * alpha.width,
    );
    const y = Math.floor(
      ((start.y + (end.y - start.y) * t) / fruit.h + 0.5) * alpha.height,
    );
    if (
      x >= 0 &&
      y >= 0 &&
      x < alpha.width &&
      y < alpha.height &&
      alpha.data[(y * alpha.width + x) * 4 + 3] > 32
    )
      return true;
  }
  return false;
}
// Polygon for each half-plane through a cut. Used by Canvas.clip on the original sprite.
export function halfPolygon(
  angle: number,
  side: number,
  extent = 1000,
): Point[] {
  const d = { x: Math.cos(angle) * extent, y: Math.sin(angle) * extent };
  const n = {
    x: -Math.sin(angle) * extent * side,
    y: Math.cos(angle) * extent * side,
  };
  return [
    { x: -d.x, y: -d.y },
    { x: d.x, y: d.y },
    { x: d.x + n.x, y: d.y + n.y },
    { x: -d.x + n.x, y: -d.y + n.y },
  ];
}
