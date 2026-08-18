(() => {
  "use strict";

  // Each book is one continuous mp3 attached as a GitHub Release asset.
  // Streamed straight from GitHub over HTTP range requests — nothing is
  // downloaded/stored on the phone.
  const REPO_OWNER = "katyastg";
  const REPO_NAME = "audiobook-player";

  const PROGRESS_KEY = "ab_progress_v3";
  const LAST_BOOK_KEY = "ab_last_book_v3";
  const SAVE_INTERVAL_MS = 5000;
  const TAIL_BUFFER_SEC = 30; // don't randomly land in the very last bit of a book

  const audio = document.getElementById("player");
  const randomPlayBtn = document.getElementById("randomPlayBtn");
  const bookListEl = document.getElementById("bookList");
  const emptyStateEl = document.getElementById("emptyState");
  const timerCountdownEl = document.getElementById("timerCountdown");
  const timerCancelBtn = document.getElementById("timerCancelBtn");

  let books = [];
  let currentBook = null;
  let draggingBookId = null;
  let saveTimer = null;
  let sleepTimeoutId = null;
  let sleepCountdownId = null;
  let sleepEndsAt = null;

  // book.id -> { li, playBtn, seek, time }
  const bookEls = {};

  function bookUrl(book) {
    return (
      "https://github.com/" +
      REPO_OWNER +
      "/" +
      REPO_NAME +
      "/releases/download/" +
      book.tag +
      "/" +
      book.file
    );
  }

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
    Object.keys(bookEls).forEach((k) => delete bookEls[k]);

    if (!books.length) {
      emptyStateEl.hidden = false;
      return;
    }
    emptyStateEl.hidden = true;

    books.forEach((book) => {
      const li = document.createElement("li");
      li.className = "book-item";
      li.dataset.bookId = book.id;

      const title = document.createElement("div");
      title.className = "book-title";
      title.textContent = book.title;

      const row = document.createElement("div");
      row.className = "book-row";

      const playBtn = document.createElement("button");
      playBtn.type = "button";
      playBtn.className = "book-play-btn";
      playBtn.textContent = "▶";
      playBtn.setAttribute("aria-label", "Играть");

      const seek = document.createElement("input");
      seek.type = "range";
      seek.className = "book-seek";
      seek.min = "0";
      seek.max = String(Math.floor(book.durationSeconds || 0));
      seek.value = "0";

      const time = document.createElement("span");
      time.className = "book-time";

      row.appendChild(playBtn);
      row.appendChild(seek);
      row.appendChild(time);

      li.appendChild(title);
      li.appendChild(row);

      bookEls[book.id] = { li, playBtn, seek, time };

      li.addEventListener("click", () => handlePlayBook(book));

      playBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        handlePlayBook(book);
      });

      seek.addEventListener("click", (e) => e.stopPropagation());
      seek.addEventListener("pointerdown", () => {
        draggingBookId = book.id;
      });
      seek.addEventListener("pointerup", () => {
        draggingBookId = null;
      });

      seek.addEventListener("input", (e) => {
        e.stopPropagation();
        const val = Number(seek.value);
        if (currentBook && currentBook.id === book.id) {
          audio.currentTime = val;
        }
        renderTimeLabel(book, val, currentBook && currentBook.id === book.id);
      });

      seek.addEventListener("change", (e) => {
        e.stopPropagation();
        draggingBookId = null;
        const val = Number(seek.value);
        if (!currentBook || currentBook.id !== book.id) {
          playBook(book, val);
        }
      });

      bookListEl.appendChild(li);

      refreshBookRow(book);
    });
  }

  function currentSeconds(book) {
    if (currentBook && currentBook.id === book.id) return audio.currentTime;
    return getProgress(book.id).t || 0;
  }

  function renderTimeLabel(book, seconds, isCurrentish) {
    const refs = bookEls[book.id];
    if (!refs) return;
    if (isCurrentish || seconds > 5) {
      refs.time.textContent = formatTime(seconds) + " / " + formatTime(book.durationSeconds);
    } else {
      refs.time.textContent = formatTime(book.durationSeconds);
    }
  }

  function refreshBookRow(book) {
    const refs = bookEls[book.id];
    if (!refs) return;
    const isCurrent = !!(currentBook && currentBook.id === book.id);
    const seconds = currentSeconds(book);

    if (draggingBookId !== book.id) {
      refs.seek.value = String(Math.floor(Math.min(seconds, book.durationSeconds || seconds)));
    }
    renderTimeLabel(book, seconds, isCurrent);
    refs.playBtn.textContent = isCurrent && !audio.paused ? "⏸" : "▶";
    refs.li.classList.toggle("playing", isCurrent);
  }

  function refreshAllRows() {
    books.forEach(refreshBookRow);
  }

  // ---------- playback ----------

  function handlePlayBook(book) {
    if (currentBook && currentBook.id === book.id) {
      if (audio.paused) {
        const p = audio.play();
        if (p && p.catch) p.catch(() => {});
      } else {
        audio.pause();
      }
    } else {
      const prog = getProgress(book.id);
      playBook(book, prog.t || 0);
    }
  }

  // Kept intentionally synchronous up to the audio.play() call — mobile
  // browsers only allow starting playback if play() runs inside the same
  // call stack as the user gesture (the click). Waiting for
  // "loadedmetadata" before calling play() (the old approach) loses that
  // gesture on iOS/Android and play() silently does nothing.
  function playBook(book, atSeconds) {
    currentBook = book;
    localStorage.setItem(LAST_BOOK_KEY, book.id);

    const startAt = Math.max(0, atSeconds || 0);

    const onReady = () => {
      audio.removeEventListener("loadedmetadata", onReady);
      if (startAt > 0 && isFinite(audio.duration)) {
        audio.currentTime = Math.min(startAt, Math.max(0, audio.duration - 1));
      }
    };

    audio.pause();
    audio.src = bookUrl(book);
    audio.addEventListener("loadedmetadata", onReady, { once: true });
    audio.load();

    const playPromise = audio.play();
    if (playPromise && playPromise.catch) playPromise.catch(() => {});

    refreshAllRows();
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

  audio.addEventListener("timeupdate", () => {
    if (!currentBook || !isFinite(audio.duration)) return;
    refreshBookRow(currentBook);
  });

  audio.addEventListener("play", () => {
    if (currentBook) refreshBookRow(currentBook);
  });
  audio.addEventListener("pause", () => {
    persistCurrentPosition();
    refreshAllRows();
  });
  audio.addEventListener("ended", () => {
    if (currentBook) {
      saveProgress(currentBook.id, 0);
      const ended = currentBook;
      currentBook = null;
      refreshBookRow(ended);
    }
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

    timerCountdownEl.hidden = false;
    timerCancelBtn.hidden = false;
    updateSleepCountdown();
    sleepCountdownId = setInterval(updateSleepCountdown, 1000);
  }

  function updateSleepCountdown() {
    if (!sleepEndsAt) return;
    const remaining = Math.max(0, Math.round((sleepEndsAt - Date.now()) / 1000));
    timerCountdownEl.textContent = formatTime(remaining);
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
    timerCountdownEl.hidden = true;
    timerCancelBtn.hidden = true;
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
