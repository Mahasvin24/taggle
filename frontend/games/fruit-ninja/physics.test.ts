import { test } from "node:test";
import assert from "node:assert/strict";
import { sweptHit, pose, halfPolygon } from "./physics.ts";
const data = new Uint8ClampedArray(10 * 10 * 4);
for (let y = 3; y < 7; y++)
  for (let x = 3; x < 7; x++) data[(y * 10 + x) * 4 + 3] = 255;
const alpha = { width: 10, height: 10, data };
test("fast strokes hit opaque pixels and miss transparent padding", () => {
  const fruit = { x: 100, y: 100, angle: 0, w: 100, h: 100 };
  assert.ok(sweptHit({ x: 0, y: 100 }, { x: 200, y: 100 }, fruit, alpha));
  assert.ok(!sweptHit({ x: 40, y: 55 }, { x: 160, y: 55 }, fruit, alpha));
  assert.ok(
    sweptHit(
      { x: 0, y: 100 },
      { x: 200, y: 100 },
      { ...fruit, angle: Math.PI / 3 },
      alpha,
    ),
  );
});
test("one stroke can hit multiple independent fruit", () => {
  assert.equal(
    [70, 170].filter((x) =>
      sweptHit(
        { x: 0, y: 100 },
        { x: 250, y: 100 },
        { x, y: 100, angle: 0.7, w: 90, h: 90 },
        alpha,
      ),
    ).length,
    2,
  );
});
test("flight starts and ends below the arena, reaches visible apex, and cut planes oppose", () => {
  const p = {
    spawn_ms: 800,
    flight_ms: 3200,
    lane: 0.5,
    drift: 0,
    rotation: 0,
    spin: 0,
    width: 100,
    height: 100,
  };
  assert.ok(pose(p, 800, 1000, 500).y > 500);
  assert.ok(pose(p, 4000, 1000, 500).y > 500);
  for (const [width, height] of [[1000, 500], [350, 410]]) {
    const apex = pose(p, 2400, width, height);
    assert.ok(apex.y < height / 2, "fruit reaches the upper playfield");
    assert.ok(apex.y - apex.h / 2 >= 91, "fruit clears the HUD, including on a phone");
  }
  assert.equal(halfPolygon(0, 1)[2].y, -halfPolygon(0, -1)[2].y);
});
