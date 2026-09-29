import { Howl } from "howler";
import { readPrefs } from "./prefs.js";

const FILES = {
  tick: "/sounds/tick.wav",
  correct: "/sounds/correct.wav",
  wrong: "/sounds/wrong.wav",
  complete: "/sounds/complete.wav",
};

const cache = new Map();

function clip(name) {
  let sound = cache.get(name);
  if (!sound) {
    // preload starts the download. Howler will not fetch a clip on play()
    // when preload is false, so the file would never load.
    sound = new Howl({ src: [FILES[name]], preload: true });
    cache.set(name, sound);
  }
  return sound;
}

export function playSound(name) {
  const prefs = readPrefs();
  if (!prefs.sound || !FILES[name]) {
    return;
  }
  const sound = clip(name);
  sound.volume(name === "tick" ? prefs.volume * 0.35 : prefs.volume);
  sound.play();
}
