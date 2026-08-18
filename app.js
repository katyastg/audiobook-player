(() => {
  "use strict";

  const PROGRESS_KEY = "ab_progress_v1";
  const LAST_BOOK_KEY = "ab_last_book_v1";
  const SAVE_INTERVAL_MS = 5000;
  const TAIL_BUFFER_SEC = 20; // don't randomly land in the very last few seconds

  const audio = document.getElementById("player");
  const randomPlayBtn = document.getElementById("randomPlayBtn");
  const nowPlaying = document.getElementById("nowPlaying");
  const npTitle = document.getElementById("npTitle");
  const npCurrent = document.getElementById("npCurrent");
  const npDuration = document.getElementById("npDuration");
  const seekBar = document.getElementById("seekBar");
  const playPauseBtn = document.getElementById("playPauseBtn");
  const bookListEl = document.getElementById("bookList");
  const emptyStateEl = document.getElementById("emptyState");
  const timerStatusEl = document.getElementById("timerStatus");
  const timerCountdownEl = document.getElementById("timerCountdown");
  const timerCancelBtn = document.getElementById("timerCancelBtn");

  let books = [];
  let currentBook = null;
  let saveTimer = null;
  let sleepTimeoutId = null;
  let sleepCountdownId = null;
  let sleepEndsAt = null;

  // ---------- progress storage ----------

  function readAllProgress() {
    try {
      return JSON.parse(localStorage.getItem(PROGRESS_KEY)) || {};
    } catch (e) {
      return {};
    }
  }

  function getProgress(bookId) {
    const all = readAllProgress();
    return all[bookId] || { t: 0 };
  }

  function saveProgress(bookId, t) {
    const all = readAllProgress();
    all[bookId] = { t: t, ts: new Date().toISOString() };
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(all));
  }

  // ---------- formatting ----------

  function formatTime(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) {
      return h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    }
    return m + ":" + String(s).padStart(2, "0");
  }

  // ---------- books ----------

  async function loadBooks() {
    try {
      const res = await fetch("books.json", { cache: "no-store" });
      books = await res.json();
    } catch (e) {
      books = [];
    }
    renderBookList();
  }

  function renderBookList() {
    bookListEl.innerHTML = "";
    if (!books.length) {
      emptyStateEl.hidden = false;
      return;
    }
    emptyStateEl.hidden = true;

    books.forEach((book) => {
      const li = document.createElement("li");
      li.className = "book-item";
      li.dataset.bookId = book.id;

      const info = document.createElement("div");
      info.className = "book-info";

      const title = document.createElement("div");
      title.className = "book-title";
      title.textContent = book.title;

      const progress = document.createElement("div");
      progress.className = "book-progress";
      const p = getProgress(book.id);
      if (p.t && p.t > 5) {
        progress.textContent = "продолжить с " + formatTime(p.t);
      } else {
        progress.textContent = "не начато";
      }

      info.appendChild(title);
      info.appendChild(progress);

      const icon = document.createElement("div");
      icon.className = "book-play-icon";
      icon.textContent = "▶";

      li.appendChild(info);
      li.appendChild(icon);

      li.addEventListener("click", () => {
        const prog = getProgress(book.id);
        playBook(book, prog.t || 0);
      });

      bookListEl.appendChild(li);
    });

    highlightPlayingBook();
  }

  function highlightPlayingBook() {
    Array.from(bookListEl.children).forEach((li) => {
      li.classList.toggle("playing", currentBook && li.dataset.bookId === currentBook.id);
    });
  }

  // ---------- playback ----------

  function playBook(book, atSeconds) {
    currentBook = book;
    localStorage.setItem(LAST_BOOK_KEY, book.id);

    nowPlaying.hidden = false;
    npTitle.textContent = book.title;
    highlightPlayingBook();

    const startAt = Math.max(0, atSeconds || 0);

    const onReady = () => {
      audio.removeEventListener("loadedmetadata", onReady);
      if (startAt > 0 && isFinite(audio.duration)) {
        audio.currentTime = Math.min(startAt, Math.max(0, audio.duration - 1));
      }
      audio.play().catch(() => {});
    };

    audio.pause();
    audio.src = book.url;
    audio.addEventListener("loadedmetadata", onReady, { once: true });
    audio.load();

    startAutoSave();
  }

  function randomPlay() {
    if (!books.length) return;
    const book = books[Math.floor(Math.random() * books.length)];

    let offset = 0;
    if (book.durationSeconds && book.durationSeconds > TAIL_BUFFER_SEC * 2) {
      offset = Math.random() * (book.durationSeconds - TAIL_BUFFER_SEC);
    }
    playBook(book, offset);
  }

  function startAutoSave() {
    stopAutoSave();
    saveTimer = setInterval(() => {
      if (currentBook && !audio.paused) {
        saveProgress(currentBook.id, audio.currentTime);
      }
    }, SAVE_INTERVAL_MS);
  }

  function stopAutoSave() {
    if (saveTimer) {
      clearInterval(saveTimer);
      saveTimer = null;
    }
  }

  function persistCurrentPosition() {
    if (currentBook && audio.currentTime > 0) {
      saveProgress(currentBook.id, audio.currentTime);
    }
  }

  // ---------- now-playing controls ----------

  audio.addEventListener("timeupdate", () => {
    if (!isFinite(audio.duration)) return;
    npCurrent.textContent = formatTime(audio.currentTime);
    npDuration.textContent = formatTime(audio.duration);
    if (!seekBar.matches(":active")) {
      seekBar.max = Math.floor(audio.duration);
      seekBar.value = Math.floor(audio.currentTime);
    }
  });

  seekBar.addEventListener("input", () => {
    audio.currentTime = Number(seekBar.value);
  });

  playPauseBtn.addEventListener("click", () => {
    if (audio.paused) {
      audio.play().catch(() => {});
    } else {
      audio.pause();
    }
  });

  audio.addEventListener("play", () => {
    playPauseBtn.textContent = "⏸";
  });
  audio.addEventListener("pause", () => {
    playPauseBtn.textContent = "▶";
    persistCurrentPosition();
    renderBookList();
  });
  audio.addEventListener("ended", () => {
    if (currentBook) {
      saveProgress(currentBook.id, 0);
    }
    renderBookList();
  });

  // Persist position when the phone backgrounds/locks or the page is hidden.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      persistCurrentPosition();
    }
  });
  window.addEventListener("pagehide", persistCurrentPosition);

  // ---------- sleep timer ----------

  function startSleepTimer(minutes) {
    clearSleepTimer();
    sleepEndsAt = Date.now() + minutes * 60 * 1000;
    sleepTimeoutId = setTimeout(fireSleepTimer, minutes * 60 * 1000);

    document.querySelectorAll(".timer-btn").forEach((btn) => {
      btn.classList.toggle("active", Number(btn.dataset.minutes) === minutes);
    });

    timerStatusEl.hidden = false;
    updateSleepCountdown();
    sleepCountdownId = setInterval(updateSleepCountdown, 1000);
  }

  function updateSleepCountdown() {
    if (!sleepEndsAt) return;
    const remaining = Math.max(0, Math.round((sleepEndsAt - Date.now()) / 1000));
    timerCountdownEl.textContent = "Пауза через " + formatTime(remaining);
  }

  function fireSleepTimer() {
    audio.pause();
    persistCurrentPosition();
    clearSleepTimer();
  }

  function clearSleepTimer() {
    if (sleepTimeoutId) clearTimeout(sleepTimeoutId);
    if (sleepCountdownId) clearInterval(sleepCountdownId);
    sleepTimeoutId = null;
    sleepCountdownId = null;
    sleepEndsAt = null;
    timerStatusEl.hidden = true;
    document.querySelectorAll(".timer-btn").forEach((btn) => btn.classList.remove("active"));
  }

  document.querySelectorAll(".timer-btn").forEach((btn) => {
    btn.addEventListener("click", () => startSleepTimer(Number(btn.dataset.minutes)));
  });
  timerCancelBtn.addEventListener("click", clearSleepTimer);

  // ---------- wire up ----------

  randomPlayBtn.addEventListener("click", randomPlay);

  loadBooks();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }
})();
