export const axes = [
  { id: "satisfaction", left: "Disappointed", right: "Satisfied", leftEmoji: "😞", rightEmoji: "😌", prompt: "How satisfied does this customer sound?", color: "#69ac92" },
  { id: "anger", left: "Not angry", right: "Angry", leftEmoji: "😐", rightEmoji: "😠", prompt: "How angry does this customer sound?", color: "#e78b76" },
  { id: "happiness", left: "Sad", right: "Happy", leftEmoji: "😢", rightEmoji: "😄", prompt: "How happy does this customer sound?", color: "#d4aa47" },
  { id: "excitement", left: "Bored", right: "Excited", leftEmoji: "😴", rightEmoji: "🤩", prompt: "How excited does this customer sound?", color: "#a18bd2" },
] as const;

export type AxisId = typeof axes[number]["id"];
export type EmotionAxis = typeof axes[number];
export const getAxis = (id: string | undefined): EmotionAxis => axes.find(a => a.id === id) ?? axes[0];
export const randomAxis = (): AxisId => axes[Math.floor(Math.random() * axes.length)].id;
export const feeling = (value: number, axis: EmotionAxis) => value < 20 ? `Mostly ${axis.left.toLowerCase()}` : value < 40 ? `Leaning ${axis.left.toLowerCase()}` : value <= 60 ? "A bit of both" : value < 80 ? `Leaning ${axis.right.toLowerCase()}` : `Very ${axis.right.toLowerCase()}`;
