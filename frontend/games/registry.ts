import FruitNinja from "./fruit-ninja/game";

// Add each game's metadata and entry component here to put it on the home page.
export const games = [
  {
    slug: "fruit-ninja",
    title: "Fruit Ninja",
    description: "A fruity twist on data labeling. Tell fresh fruit from spoiled fruit.",
    icon: "🍎",
    previewLabel: "Fresh or spoiled?",
    status: "Coming soon",
    component: FruitNinja,
  },
];
