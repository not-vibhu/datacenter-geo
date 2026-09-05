const paths = {
  server:
    '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M11 6.5h6M11 17.5h6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  arrow: '<path d="M5 19 19 5M5 5h14v14"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  crosshair:
    '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  link: '<path d="m10 13 4-4M8 15l-2 2a4 4 0 0 1-5-5l4-4a4 4 0 0 1 5 0m4 1 2-2a4 4 0 0 1 5 5l-4 4a4 4 0 0 1-5 0"/>',
  frame:
    '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5"/><circle cx="12" cy="12" r="3"/>',
  polygon:
    '<path d="m5 5 14 2-3 12-12-3Z"/><rect x="3" y="3" width="4" height="4"/><rect x="17" y="5" width="4" height="4"/><rect x="14" y="17" width="4" height="4"/><rect x="2" y="14" width="4" height="4"/>',
  square: '<rect x="4" y="4" width="16" height="16" rx="1"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  hand: '<path d="M8 13V5a2 2 0 0 1 4 0v7-8a2 2 0 0 1 4 0v8-5a2 2 0 0 1 4 0v8c0 4-3 7-7 7-3 0-5-2-7-5l-3-5c-1-2 2-3 3-1l2 2Z"/>',
  map: '<path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16"/>',
  satellite:
    '<path d="m7 8 5-5 9 9-5 5ZM3 15l6 6m-5-9 8 8M2 20h2v2"/><path d="m13 5 4-4 6 6-4 4M5 13l-4 4 6 6 4-4"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8Zm-10 10 10 5 10-5M2 18l10 5 10-5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
  bolt: '<path d="m13 2-9 12h7l-1 8 10-13h-7Z"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  edit: '<path d="m4 16 12-12 4 4-12 12H4Zm10-10 4 4"/>',
  book: '<path d="M5 3h14v19l-7-5-7 5Z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
};
export const icon = (name) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.pin}</svg>`;
export function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });
}
