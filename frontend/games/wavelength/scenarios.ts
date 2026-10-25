export const scenarios = [
  { id: "gas-station", title: "A stop at the gas station", prompt: "You stopped to fill up and pick up a snack." },
  { id: "clothes-shopping", title: "Shopping for clothes", prompt: "You visited a clothing store to find an outfit." },
  { id: "grocery-run", title: "The weekly grocery run", prompt: "You went to the supermarket for your weekly groceries." },
  { id: "coffee-stop", title: "Getting your morning coffee", prompt: "You popped into a café for a drink before starting your day." },
  { id: "dinner-out", title: "Dinner at a restaurant", prompt: "You tried a restaurant with a friend." },
  { id: "online-order", title: "Opening an online order", prompt: "Something you ordered online has arrived." },
  { id: "hotel-stay", title: "A weekend at a hotel", prompt: "You booked a hotel for a short getaway." },
  { id: "movie-night", title: "A night at the movies", prompt: "You went to the cinema to see a film." },
  { id: "food-delivery", title: "Ordering food delivery", prompt: "You ordered dinner to your home." },
  { id: "haircut", title: "Getting a haircut", prompt: "You visited a salon or barber for a haircut." },
  { id: "train-ride", title: "Taking the train", prompt: "You took a train to visit another town." },
  { id: "new-app", title: "Trying a new app", prompt: "You downloaded an app to help with an everyday task." },
] as const;

export type Scenario = typeof scenarios[number];
export const getScenario = (id: string | undefined) => scenarios.find(s => s.id === id);
export function randomScenario(previousId?: string): Scenario {
  const choices = scenarios.filter(s => s.id !== previousId);
  return choices[Math.floor(Math.random() * choices.length)];
}
