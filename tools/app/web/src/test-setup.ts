import '@testing-library/jest-dom/vitest'
import { configure } from '@testing-library/react'

// Several suites drop a file and await an async FileReader (see the File.text
// polyfill below). Testing Library's 1s default for waitFor/findBy* is tight
// enough to expire under full-suite load on a busy machine, which surfaced as
// intermittent failures that always passed when the file was run alone — first
// in GlobalDropOverlay, then in App. Raising the shared budget fixes the whole
// class; it costs nothing when the assertion resolves promptly, as it normally
// does.
configure({ asyncUtilTimeout: 5000 })

// jsdom has no ResizeObserver; a no-op stub is enough for components that
// only use it to react to real layout changes.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
}

// jsdom has no window.matchMedia; App reads it once for the initial theme
// (prefers-color-scheme). A minimal stub (always "no match") is enough since
// no suite exercises the OS dark-mode branch itself.
if (typeof window.matchMedia === 'undefined') {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

// Polyfill File.text() for jsdom
if (!File.prototype.text) {
  Object.defineProperty(File.prototype, 'text', {
    value: function () {
      return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as string)
        reader.onerror = () => reject(reader.error)
        reader.readAsText(this)
      })
    },
  })
}
