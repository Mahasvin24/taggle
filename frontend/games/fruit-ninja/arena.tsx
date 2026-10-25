"use client";
import { useEffect, useRef, useState } from "react";
import {
  halfPolygon,
  pose,
  sweptHit,
  type Alpha,
  type Point,
  type Pose,
} from "./physics";
import type { Judgment, Round, Presentation } from "./types";
import styles from "./game.module.css";

type Sprite = { image: HTMLImageElement; alpha: Alpha };
type Half = {
  sprite: Sprite;
  pose: Pose;
  angle: number;
  side: number;
  born: number;
  vx: number;
  vy: number;
  spin: number;
};
type Particle = Point & { vx: number; vy: number; born: number; size: number };
export type Hud = {
  elapsed: number;
  fresh: number;
  rotten: number;
  resolved: number;
};
type Props = {
  round: Round;
  paused: boolean;
  muted: boolean;
  reduced: boolean;
  onReady: () => Promise<void>;
  onJudgment: (event: Judgment) => void;
  onTick: (hud: Hud) => void;
  onEnd: () => void;
  onPause: () => void;
};

export default function Arena(props: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const current = useRef(props);
  const [loading, setLoading] = useState("Getting your fruit ready…");
  useEffect(() => {
    current.current = props;
  });
  useEffect(() => {
    let cancelled = false,
      frame = 0;
    const el = canvas.current!;
    const ctx = el.getContext("2d")!;
    let width = 1000,
      height = 540,
      time = 0,
      last = 0,
      lastHud = 0,
      ended = false,
      ready = false,
      countdown = 3000,
      strokeCuts = 0,
      lastCutAt = -Infinity,
      bestSlice = 0;
    let sliceNotice: { text: string; born: number; x: number; y: number } | null = null;
    const resolved = new Set<string>(),
      sprites = new Map<string, Sprite>(),
      halves: Half[] = [],
      particles: Particle[] = [];
    let trail: (Point & { born: number })[] = [],
      pointer: Point | null = null,
      activePointer: number | null = null;
    let fresh = 0,
      rotten = 0;
    let audio: AudioContext | null = null;
    const resize = () => {
      const box = el.getBoundingClientRect();
      width = box.width;
      height = box.height;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      el.width = width * dpr;
      el.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    resize();
    const sound = (combo = 1) => {
      if (current.current.muted) return;
      try {
        audio ??= new AudioContext();
        void audio.resume();
        const osc = audio.createOscillator(),
          gain = audio.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(420 + Math.min(combo - 1, 4) * 120, audio.currentTime);
        osc.frequency.exponentialRampToValueAtTime(
          90,
          audio.currentTime + 0.12,
        );
        gain.gain.setValueAtTime(0.065, audio.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.14);
        osc.connect(gain);
        gain.connect(audio.destination);
        osc.start();
        osc.stop(audio.currentTime + 0.15);
      } catch {
        /* Audio availability must not block labels. */
      }
    };
    const resolve = (
      p: Presentation,
      action: "slice" | "pass",
      direction = 0,
    ) => {
      if (resolved.has(p.id)) return;
      resolved.add(p.id);
      if (action === "slice") rotten++;
      else fresh++;
      current.current.onJudgment({
        event_id: crypto.randomUUID(),
        presentation_id: p.id,
        action,
        client_timestamp: new Date().toISOString(),
        elapsed_ms: Math.min(
          props.round.duration_ms,
          Math.floor(action === "pass" ? p.spawn_ms + p.flight_ms : time),
        ),
        exposure_ms:
          action === "pass"
            ? p.flight_ms
            : Math.max(0, Math.round(time - p.spawn_ms)),
      });
      current.current.onTick({
        elapsed: time,
        fresh,
        rotten,
        resolved: resolved.size,
      });
      if (action === "slice") {
        if (time - lastCutAt > 450) strokeCuts = 0;
        strokeCuts++;
        lastCutAt = time;
        sound(strokeCuts);
        const fruit = pose(p, time, width, height),
          sprite = sprites.get(p.asset_id)!;
        if (strokeCuts >= 2) {
          bestSlice = Math.max(bestSlice, strokeCuts);
          sliceNotice = {
            text: strokeCuts === 2 ? "Double slice!" : `${strokeCuts} fruit combo!`,
            born: time,
            x: Math.max(100, Math.min(width - 100, fruit.x)),
            y: Math.max(130, fruit.y - 80),
          };
        }
        for (const side of [-1, 1])
          halves.push({
            sprite,
            pose: { ...fruit },
            angle: direction - fruit.angle,
            side,
            born: time,
            vx: -Math.sin(direction) * side * 105,
            vy: Math.cos(direction) * side * 105 - 45,
            spin: current.current.reduced ? 0 : side * 1.6,
          });
        if (!current.current.reduced)
          for (let i = 0; i < 14; i++) {
            const a = Math.random() * Math.PI * 2,
              speed = 40 + Math.random() * 170;
            particles.push({
              x: fruit.x,
              y: fruit.y,
              vx: Math.cos(a) * speed,
              vy: Math.sin(a) * speed,
              born: time,
              size: 2 + Math.random() * 5,
            });
          }
      }
    };
    const point = (event: PointerEvent) => {
      const r = el.getBoundingClientRect();
      return { x: event.clientX - r.left, y: event.clientY - r.top };
    };
    const stroke = (a: Point, b: Point) => {
      if (!ready || ended || countdown > 0 || current.current.paused) return;
      if (!trail.length) trail.push({ ...a, born: time });
      trail.push({ ...b, born: time });
      for (const p of props.round.presentations) {
        if (
          resolved.has(p.id) ||
          time < p.spawn_ms ||
          time >= p.spawn_ms + p.flight_ms
        )
          continue;
        const fruit = pose(p, time, width, height),
          sprite = sprites.get(p.asset_id)!;
        if (sweptHit(a, b, fruit, sprite.alpha))
          resolve(p, "slice", Math.atan2(b.y - a.y, b.x - a.x));
      }
    };
    const down = (e: PointerEvent) => {
      if (
        current.current.paused ||
        !ready ||
        e.button > 0 ||
        activePointer !== null
      )
        return;
      activePointer = e.pointerId;
      el.setPointerCapture(e.pointerId);
      pointer = point(e);
      trail = [];
      strokeCuts = 0;
      stroke(pointer, pointer);
      e.preventDefault();
    };
    const move = (e: PointerEvent) => {
      if (e.pointerId !== activePointer || !pointer) return;
      const samples = e.getCoalescedEvents?.() || [e];
      for (const sample of samples.length ? samples : [e]) {
        const next = point(sample);
        stroke(pointer, next);
        pointer = next;
      }
      e.preventDefault();
    };
    const up = () => {
      activePointer = null;
      pointer = null;
      strokeCuts = 0;
    };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    el.addEventListener("lostpointercapture", up);
    const blur = () => {
      up();
      current.current.onPause();
    };
    const visibility = () => {
      if (document.hidden) blur();
    };
    window.addEventListener("blur", blur);
    document.addEventListener("visibilitychange", visibility);
    const draw = (stamp: number) => {
      if (cancelled) return;
      const dt = last ? stamp - last : 0;
      const stalled = dt > 500;
      if (stalled && ready && !current.current.paused && !ended)
        current.current.onPause();
      last = stamp;
      if (ready && !current.current.paused && !ended && !stalled) {
        if (countdown > 0) countdown = Math.max(0, countdown - dt);
        else time = Math.min(props.round.duration_ms, time + dt);
      }
      if (current.current.paused) up();
      ctx.clearRect(0, 0, width, height);
      // A plain, light ground preserves the visible condition of every photo.
      ctx.fillStyle = "#d9e8ed";
      ctx.fillRect(0, 0, width, height);
      for (const p of props.round.presentations) {
        if (
          resolved.has(p.id) ||
          time < p.spawn_ms ||
          time >= p.spawn_ms + p.flight_ms
        )
          continue;
        const fruit = pose(p, time, width, height),
          sprite = sprites.get(p.asset_id);
        if (!sprite) continue;
        ctx.save();
        ctx.translate(fruit.x, fruit.y);
        ctx.rotate(fruit.angle);
        ctx.shadowColor = "#31555c22";
        ctx.shadowBlur = 8;
        ctx.shadowOffsetY = 4;
        ctx.drawImage(
          sprite.image,
          -fruit.w / 2,
          -fruit.h / 2,
          fruit.w,
          fruit.h,
        );
        ctx.restore();
      }
      for (let i = halves.length - 1; i >= 0; i--) {
        const h = halves[i],
          age = (time - h.born) / 1000;
        if (age > 1.3) {
          halves.splice(i, 1);
          continue;
        }
        ctx.save();
        ctx.globalAlpha = 1 - age / 1.3;
        ctx.translate(
          h.pose.x + h.vx * age,
          h.pose.y + h.vy * age + 240 * age * age,
        );
        ctx.rotate(h.pose.angle + h.spin * age);
        const poly = halfPolygon(h.angle, h.side);
        ctx.beginPath();
        poly.forEach((p, j) =>
          j ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y),
        );
        ctx.closePath();
        ctx.clip();
        ctx.drawImage(
          h.sprite.image,
          -h.pose.w / 2,
          -h.pose.h / 2,
          h.pose.w,
          h.pose.h,
        );
        ctx.restore();
      }
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i],
          age = (time - p.born) / 1000;
        if (age > 0.7) {
          particles.splice(i, 1);
          continue;
        }
        ctx.fillStyle = `rgba(39,121,125,${0.7 * (1 - age / 0.7)})`;
        ctx.beginPath();
        ctx.arc(
          p.x + p.vx * age,
          p.y + p.vy * age + 200 * age * age,
          p.size,
          0,
          Math.PI * 2,
        );
        ctx.fill();
      }
      trail = trail.filter((p) => time - p.born < 140);
      if (trail.length > 1) {
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        for (let i = 1; i < trail.length; i++) {
          ctx.strokeStyle = `rgba(29,111,119,${0.8 * i / trail.length})`;
          ctx.lineWidth = 2 + (8 * i) / trail.length;
          ctx.shadowBlur = 0;
          ctx.beginPath();
          ctx.moveTo(trail[i - 1].x, trail[i - 1].y);
          ctx.lineTo(trail[i].x, trail[i].y);
          ctx.stroke();
          ctx.strokeStyle = `rgba(255,255,255,${i / trail.length})`;
          ctx.lineWidth = 1 + (3 * i) / trail.length;
          ctx.stroke();
        }
        ctx.shadowBlur = 0;
      }
      if (sliceNotice && time - sliceNotice.born < 850) {
        const age = (time - sliceNotice.born) / 850;
        ctx.save();
        ctx.globalAlpha = Math.min(1, (1 - age) * 3);
        ctx.textAlign = "center";
        ctx.font = '700 32px "Barlow Condensed"';
        ctx.lineWidth = 5;
        ctx.strokeStyle = "#edf4f5";
        ctx.fillStyle = "#236b70";
        const y = sliceNotice.y - (current.current.reduced ? 0 : age * 22);
        ctx.strokeText(sliceNotice.text, sliceNotice.x, y);
        ctx.fillText(sliceNotice.text, sliceNotice.x, y);
        ctx.restore();
      }
      if (ready && countdown > 0) {
        ctx.textAlign = "center";
        ctx.fillStyle = "#203e49";
        ctx.font = '700 100px "Barlow Condensed"';
        ctx.fillText(String(Math.ceil(countdown / 1000)), width / 2, height * .48);
        ctx.font = "600 16px Barlow";
        ctx.fillText("Slice rotten. Let healthy fly.", width / 2, height * .48 + 42);
      }
      // A short end-of-round flourish, with no changes to saved judgments.
      el.dataset.bestSlice = String(bestSlice);
      if (ready && countdown === 0 && !current.current.paused && !ended && !stalled) {
        for (const p of props.round.presentations)
          if (time >= p.spawn_ms + p.flight_ms && !resolved.has(p.id))
            resolve(p, "pass");
        if (time - lastHud > 80 || time === props.round.duration_ms) {
          lastHud = time;
          current.current.onTick({
            elapsed: time,
            fresh,
            rotten,
            resolved: resolved.size,
          });
        }
        if (time >= props.round.duration_ms) {
          ended = true;
          up();
          current.current.onEnd();
        }
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    (async () => {
      try {
        await Promise.all(
          props.round.presentations.map(async (p) => {
            if (sprites.has(p.asset_id)) return;
            const img = new Image();
            img.src = p.url;
            await img.decode();
            const off = document.createElement("canvas");
            off.width = img.naturalWidth;
            off.height = img.naturalHeight;
            const oc = off.getContext("2d", { willReadFrequently: true })!;
            oc.drawImage(img, 0, 0);
            sprites.set(p.asset_id, {
              image: img,
              alpha: {
                width: off.width,
                height: off.height,
                data: oc.getImageData(0, 0, off.width, off.height).data,
              },
            });
          }),
        );
        if (cancelled) return;
        await current.current.onReady();
        if (!cancelled) {
          ready = true;
          setLoading("");
        }
      } catch (error) {
        if (!cancelled)
          setLoading(
            `Could not load the fruit. ${error instanceof Error ? error.message : "Try again."}`,
          );
      }
    })();
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      el.removeEventListener("lostpointercapture", up);
      window.removeEventListener("blur", blur);
      document.removeEventListener("visibilitychange", visibility);
      void audio?.close();
    };
  }, [props.round]);
  return (
    <div className={styles.arena}>
      <canvas
        ref={canvas}
        aria-label="Fruit arena. Hold and drag to slice rotten fruit; let healthy fruit fly."
      />
      {loading && (
        <div className={styles.arenaMessage}>
          <span className={styles.loader} />
          <p>{loading}</p>
        </div>
      )}
    </div>
  );
}
