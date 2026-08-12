import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  // El tema se persiste en localStorage y se refleja en <html>: sin limpiar las dos cosas, un
  // test que alterna el tema decide el resultado del siguiente.
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})
