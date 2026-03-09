import '@testing-library/jest-dom'

// jsdom은 scrollIntoView를 구현하지 않으므로 no-op mock
window.HTMLElement.prototype.scrollIntoView = () => {}
