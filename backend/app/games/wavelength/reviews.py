"""Original demo text, not customer data or independently validated ground truth.

Reference scores are authored anchors for game feedback. Preserve human judgments
independently; these anchors must never be described as crowd consensus.
"""

REFERENCE_VERSION = "demo-v2-emotions"
SOURCE = "authored_demo"

AXES = [
    {"id": "satisfaction", "left": "Disappointed", "right": "Satisfied"},
    {"id": "anger", "left": "Not angry", "right": "Angry"},
    {"id": "happiness", "left": "Sad", "right": "Happy"},
    {"id": "excitement", "left": "Bored", "right": "Excited"},
]
AXES_BY_ID = {axis["id"]: axis for axis in AXES}

REVIEWS = [
    {
        "id": "review-01", "category": "Dining",
        "text": "The food was lovely, but after waiting forty minutes for the bill, I mostly just wanted to leave.",
        "reference_score": 42,
        "reference_note": "Good food is offset by a frustrating wait. The ending leaves a mildly negative overall impression.",
    },
    {
        "id": "review-02", "category": "Shopping",
        "text": "Exactly what I ordered, delivered a day early. Even the packaging was easy to recycle. Already buying another.",
        "reference_score": 94,
        "reference_note": "Several positives and a clear intention to buy again make this strongly satisfied.",
    },
    {
        "id": "review-03", "category": "Travel",
        "text": "A beautiful lobby. Unfortunately, I was paying to sleep in the room, where the air conditioner sounded like a lawnmower.",
        "reference_score": 15,
        "reference_note": "The lobby praise is a setup for criticism. Noise undermines the core purpose of the hotel stay.",
    },
    {
        "id": "review-04", "category": "Apps",
        "text": "It does what it says. No surprises, no complaints. I open it when I need it and then forget about it.",
        "reference_score": 57,
        "reference_note": "Functional and uneventful. There is mild satisfaction but little enthusiasm.",
    },
    {
        "id": "review-05", "category": "Services",
        "text": "I was dreading the call, but Maya fixed everything in five minutes and explained what had happened. Such a relief.",
        "reference_score": 90,
        "reference_note": "The initial worry is resolved by helpful service. Relief and specific praise dominate.",
    },
    {
        "id": "review-06", "category": "Entertainment",
        "text": "The tickets weren't cheap, and the opening dragged. By the final song, though, we were all on our feet.",
        "reference_score": 77,
        "reference_note": "The enthusiastic ending outweighs the price and slow opening, without erasing them.",
    },
    {
        "id": "review-07", "category": "Dining",
        "text": "Cold coffee, stale pastry, and a server who seemed annoyed that I mentioned either. A pretty impressive hat trick.",
        "reference_score": 5,
        "reference_note": "The last sentence is sarcastic. Product and service complaints combine into strong disappointment.",
    },
    {
        "id": "review-08", "category": "Shopping",
        "text": "The jacket fits well and the fabric feels nice. The color is a little different from the photo, but I'm keeping it.",
        "reference_score": 72,
        "reference_note": "The customer likes the main qualities and keeps the item despite a small mismatch.",
    },
    {
        "id": "review-09", "category": "Travel",
        "text": "We got there safely and on time. Legroom was tight, but for that fare I can't really complain.",
        "reference_score": 65,
        "reference_note": "The basic expectations are met. The price softens the comfort complaint.",
    },
    {
        "id": "review-10", "category": "Apps",
        "text": "Love the new design. Love it even more when the app lets me log in, which so far has happened once this week.",
        "reference_score": 18,
        "reference_note": "The praise becomes sarcastic because unreliable login blocks the app's core use.",
    },
    {
        "id": "review-11", "category": "Services",
        "text": "The repair worked, but the final bill was almost double the estimate and nobody called to check with me first.",
        "reference_score": 28,
        "reference_note": "A successful repair is outweighed by an unexpected cost and lack of communication.",
    },
    {
        "id": "review-12", "category": "Entertainment",
        "text": "Some great moments, some very forgettable ones. I don't regret watching it, but I won't be recommending it either.",
        "reference_score": 49,
        "reference_note": "Positive and negative reactions balance out, with no intention to recommend.",
    },
    {
        "id": "review-13", "category": "Dining",
        "text": "Tiny menu, tiny room, enormous flavor. We booked our next visit before dessert arrived.",
        "reference_score": 97,
        "reference_note": "The apparent negatives are affectionate. Immediate rebooking signals very high satisfaction.",
    },
    {
        "id": "review-14", "category": "Shopping",
        "text": "The headphones sound fine. For half this price I'd be happy; at full price, they're just okay.",
        "reference_score": 45,
        "reference_note": "Adequate performance is tempered by disappointing value. The overall judgment is slightly negative.",
    },
    {
        "id": "review-15", "category": "Travel",
        "text": "They lost our reservation, then found us a better room and sent up breakfast. A rough start, but they really turned it around.",
        "reference_score": 81,
        "reference_note": "The initial failure is acknowledged, but the recovery creates a clearly positive final impression.",
    },
    {
        "id": "review-16", "category": "Apps",
        "text": "Nothing loads, support hasn't replied, and my annual subscription renewed anyway. I've submitted a refund request.",
        "reference_score": 3,
        "reference_note": "Failure to function, failed support, and unwanted billing leave almost no positive signal.",
    },
    {
        "id": "review-17", "category": "Services",
        "text": "They arrived within the time window and finished the job. I wish they'd cleaned up after themselves.",
        "reference_score": 53,
        "reference_note": "The essential work was completed as promised, with a noticeable but secondary complaint.",
    },
    {
        "id": "review-18", "category": "Entertainment",
        "text": "I brought my skeptical dad. He hasn't stopped talking about the show for three days. Worth every penny.",
        "reference_score": 96,
        "reference_note": "Lasting enthusiasm and explicit value praise indicate extremely strong satisfaction.",
    },
    {
        "id": "review-19", "category": "Dining",
        "text": "Not the best pizza in town, but it's warm, reliable, and the people remember my name. It's become my Friday spot.",
        "reference_score": 82,
        "reference_note": "Modest food praise is outweighed by reliability, belonging, and repeat visits.",
    },
    {
        "id": "review-20", "category": "Shopping",
        "text": "It broke on the second use. They replaced it quickly, but now I'm nervous every time I switch it on.",
        "reference_score": 34,
        "reference_note": "Helpful replacement service only partly repairs the loss of confidence in the product.",
    },
    {
        "id": "review-21", "category": "Travel",
        "text": "The room looked just like the photos. The beach was five minutes away. It was a perfectly ordinary weekend, which was all I wanted.",
        "reference_score": 74,
        "reference_note": "Ordinary is positive here: the stay met the customer's stated needs and expectations.",
    },
    {
        "id": "review-22", "category": "Apps",
        "text": "The update added features I won't use and moved the one button I need. It still works, but using it feels like a chore now.",
        "reference_score": 31,
        "reference_note": "The app functions, but the customer describes a worse experience and ongoing frustration.",
    },
    {
        "id": "review-23", "category": "Services",
        "text": "No hard sell, clear prices, and they actually called when they said they would. I'd happily use them again.",
        "reference_score": 88,
        "reference_note": "Trust, communication, and a clear willingness to return indicate strong satisfaction.",
    },
    {
        "id": "review-24", "category": "Entertainment",
        "text": "We spent more time in line than looking at the exhibits. The kids were bored and we left before lunch.",
        "reference_score": 12,
        "reference_note": "Long waits, boredom, and an early departure indicate an experience that largely failed.",
    },
]

# These are separately authored emotional readings, not transformations of the
# satisfaction score. Relief can be happy without excitement; boredom need not
# imply anger. All remain fictional feedback anchors rather than validated truth.
# Each tuple contains anger, happiness, excitement, then their explanations.
EMOTION_READINGS = [
    (58, 39, 20, "The prolonged wait sounds frustrating, without an outright furious tone.", "Enjoyment of the food gives way to wanting to leave.", "The ending is weary and disengaged rather than enthusiastic."),
    (2, 94, 82, "There is no expressed irritation; the delivery exceeded expectations.", "Repeated praise and buying another convey delight.", "The immediate repeat purchase conveys active enthusiasm."),
    (73, 18, 15, "The sarcastic contrast between lobby and sleepless room conveys irritation.", "The core experience sounds miserable despite the attractive lobby.", "The noisy room is described with frustration, not positive anticipation."),
    (3, 58, 15, "The reviewer explicitly has no complaints.", "The tone is content but emotionally restrained.", "Forgetting the app after use suggests low excitement, despite adequate function."),
    (5, 90, 48, "The worry was resolved; the closing tone is appreciative rather than angry.", "Quick help produces clear relief and gratitude.", "Relief is positive, but the reviewer is not describing thrill or anticipation."),
    (12, 84, 95, "Early pacing and price are complaints, but the ending is celebratory.", "Being on their feet at the end conveys a joyful final impression.", "The final song gets everyone on their feet: an unusually direct excitement cue."),
    (94, 7, 8, "Three complaints and biting sarcasm convey pronounced anger.", "Neither food nor service gives the reviewer anything to enjoy.", "The sarcastic hat trick describes irritation, not an entertaining experience."),
    (10, 74, 51, "The color mismatch is mild and accepted.", "Fit and fabric please the reviewer enough to keep the jacket.", "The response is positive, though keeping an item is less enthusiastic than raving about it."),
    (9, 65, 24, "The reviewer explicitly softens the legroom complaint with the fare.", "Getting there safely and on time leaves a reasonably content tone.", "This is practical acceptance of travel, not an exhilarating trip."),
    (81, 17, 14, "Repeated sarcastic love language highlights irritation at failed logins.", "The attractive design does little to offset being unable to use the app.", "The design initially interests them, but login failure undercuts any enthusiasm."),
    (78, 24, 18, "An unapproved price increase sounds like a serious grievance.", "The repaired item is a positive, but the surprise bill dominates their reaction.", "The review concentrates on a dispute, with little positive engagement."),
    (5, 51, 33, "The reviewer is lukewarm rather than annoyed.", "Not regretting it and not recommending it express a balanced emotional reaction.", "Forgettable sections and no recommendation suggest limited excitement."),
    (1, 97, 94, "The tiny room and menu are affectionate setup, with no anger expressed.", "Enormous flavor and immediate rebooking convey delight.", "Booking again before dessert is a strong cue of enthusiasm and anticipation."),
    (28, 44, 19, "The complaint is restrained concern about value rather than outrage.", "The reviewer explicitly says the price prevents them from being happy.", "The sound is merely fine; there is little novelty or enthusiasm."),
    (18, 85, 64, "The reservation problem caused frustration, but the recovery largely resolves it.", "The better room and breakfast produce a grateful final impression.", "The unexpected upgrade adds some enthusiasm without making the whole stay thrilling."),
    (98, 4, 4, "Product failure, silence, and unwanted billing combine into a very angry account.", "A refund request follows an account with almost no positive feeling.", "The reviewer wants out, with no expressed excitement about continued use."),
    (30, 52, 18, "The mess is irritating, but the tone stays measured.", "The work is done, though the lack of cleanup tempers contentment.", "A routine completed job offers little stimulation or enthusiasm."),
    (1, 98, 97, "The reviewer offers praise without a grievance.", "The dad's lasting enthusiasm and worth every penny express joy.", "Talking about the show for three days is a very strong excitement cue."),
    (2, 84, 48, "The modest pizza comparison is not phrased as a grievance.", "Recognition and a comforting weekly ritual suggest warm happiness.", "Reliability and routine create attachment, but are less exciting than a novel event."),
    (36, 31, 12, "Fast replacement softens the initial frustration; worry now dominates.", "The broken item leaves lingering unease despite helpful service.", "Being nervous to switch it on is apprehension, not positive excitement."),
    (2, 78, 20, "The reviewer says the ordinary trip was exactly what they wanted.", "Met expectations and a nearby beach leave an explicitly content impression.", "Perfectly ordinary signals low excitement, which is not a negative for this reviewer."),
    (62, 29, 10, "Moving an essential button creates ongoing irritation.", "Describing use as a chore signals a diminished positive feeling.", "Unwanted features and a chore-like experience convey disengagement."),
    (1, 88, 51, "Clear communication and no pressure leave no expressed anger.", "The reviewer explicitly says they would happily return.", "Trust encourages a return, though the review is appreciative rather than exuberant."),
    (68, 13, 2, "Long queues and leaving early suggest marked frustration.", "The failed family outing leaves a downbeat impression.", "The kids are explicitly bored, and the family leaves before lunch."),
]

for review, reading in zip(REVIEWS, EMOTION_READINGS, strict=True):
    anger, happiness, excitement, anger_note, happy_note, excitement_note = reading
    review["references"] = {
        "satisfaction": {"score": review["reference_score"], "note": review["reference_note"]},
        "anger": {"score": anger, "note": anger_note},
        "happiness": {"score": happiness, "note": happy_note},
        "excitement": {"score": excitement, "note": excitement_note},
    }

BY_ID = {review["id"]: review for review in REVIEWS}


def public_reviews():
    return [{"id": r["id"], "text": r["text"], "category": r["category"], "source": SOURCE} for r in REVIEWS]
