/** Calm ambient music — rotates through up to five tracks from the server playlist. */

import { Howl } from "howler";
import { api } from "./api/client.js";
import { readPrefs } from "./prefs.js";

let playlist = null;
let index = 0;
let current = null;
let started = false;
let loading = null;

function activeTracks() {
  const tracks = playlist?.tracks || [];
  return tracks.filter((track) => String(track?.url || "").trim());
}

function stopCurrent() {
  if (!current) return;
  try {
    current.stop();
    current.unload();
  } catch {
    /* ignore */
  }
  current = null;
}

function volumeFromPrefs() {
  const prefs = readPrefs();
  if (!prefs.music || prefs.reduceMotion) return 0;
  return Math.min(1, Math.max(0, Number(prefs.musicVolume) || 0));
}

function playAt(nextIndex) {
  const tracks = activeTracks();
  if (!tracks.length || !playlist?.enabled) {
    stopCurrent();
    return;
  }
  const prefs = readPrefs();
  if (!prefs.music || prefs.reduceMotion) {
    stopCurrent();
    return;
  }
  index = ((nextIndex % tracks.length) + tracks.length) % tracks.length;
  const track = tracks[index];
  stopCurrent();
  const sound = new Howl({
    src: [track.url],
    html5: true,
    volume: volumeFromPrefs(),
    onend: () => {
      if (playlist?.rotate === false) {
        playAt(index);
        return;
      }
      playAt(index + 1);
    },
    onloaderror: () => {
      // Skip a broken URL and try the next track once.
      if (tracks.length > 1) {
        window.setTimeout(() => playAt(index + 1), 400);
      }
    },
  });
  current = sound;
  sound.play();
}

export async function loadMusicPlaylist() {
  if (loading) return loading;
  loading = api("/api/music/playlist")
    .then((data) => {
      playlist = data;
      return data;
    })
    .catch(() => {
      playlist = {
        enabled: true,
        rotate: true,
        tracks: [
          { id: "dawn", title: "Dawn", url: "/sounds/music/calm-01-dawn.wav" },
          { id: "harbor", title: "Harbor", url: "/sounds/music/calm-02-harbor.wav" },
          { id: "mist", title: "Mist", url: "/sounds/music/calm-03-mist.wav" },
          { id: "ember", title: "Ember", url: "/sounds/music/calm-04-ember.wav" },
          { id: "tide", title: "Tide", url: "/sounds/music/calm-05-tide.wav" },
        ],
      };
      return playlist;
    })
    .finally(() => {
      loading = null;
    });
  return loading;
}

export async function syncMusicFromPrefs() {
  const prefs = readPrefs();
  if (!prefs.music || prefs.reduceMotion) {
    stopCurrent();
    started = false;
    return;
  }
  if (!playlist) {
    await loadMusicPlaylist();
  }
  if (!playlist?.enabled) {
    stopCurrent();
    started = false;
    return;
  }
  if (current) {
    current.volume(volumeFromPrefs());
    if (!current.playing()) current.play();
    return;
  }
  if (!started) {
    started = true;
    playAt(index);
  }
}

export function applyMusicVolume() {
  if (current) {
    current.volume(volumeFromPrefs());
  }
}

export function stopMusic() {
  stopCurrent();
  started = false;
}

/** Call once after a user gesture if the browser blocked autoplay. */
export function unlockMusic() {
  syncMusicFromPrefs();
}
