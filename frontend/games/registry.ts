import FruitNinja from "./fruit-ninja/game";

// Add each game's metadata and entry component here to put it on the home page.
export const games = [
  {
    slug: "fruit-ninja",
    title: "Fruit Shift",
    description:
      "Slice rotten fruit. Let healthy fruit fly. Build a dataset, one shift at a time.",
    icon: "🍎",
    previewLabel: "Healthy or rotten?",
    status: "Play now",
    component: FruitNinja,
  },
];
