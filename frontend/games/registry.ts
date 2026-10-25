import FruitNinja from "./fruit-ninja/game";
import CommonGround from "./wavelength/game";

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
  {
    slug: "wavelength",
    title: "Common Ground",
    description:
      "Read between the lines. Find a review’s feeling, or challenge a friend to read your mind.",
    icon: "◴",
    previewLabel: "Disappointed, delighted, or somewhere in between?",
    status: "Play now",
    component: CommonGround,
  },
];
