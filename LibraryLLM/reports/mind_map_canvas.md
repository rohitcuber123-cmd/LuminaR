# Mind map canvas update

The document mind map now uses the available workspace width and height, fits the whole map initially, and supports zooming out below that fitted view. A centered layout balances branches on both sides and allocates vertical space to each subtree. At lower zoom, cards shrink while branch positions expand to occupy the canvas.

Fullscreen opens a viewport-sized overlay above the navigation, document sidebar, and assistant launcher. Concept details and authenticated source excerpts stay inside the overlay. Escape exits it and restores focus. Drag and wheel panning are supported; wheel panning prevents scrolling the surrounding page. Reset view fits and centers the whole map again.

Validation:

- All 332 frontend tests pass, including eight focused layout/interaction tests and the existing Knowledge Tools source-fetch integration test extended for fullscreen.
- Production build passes. Lint reports only the 19 existing warnings; none in the changed map files. The existing main bundle size warning remains.
- Browser verification used the actual CN UNIT-2 notes to produce 40 nodes and 39 connections in a temporary local preview. All nodes fit the initial fullscreen view at desktop and 375 × 812 phone dimensions. Zoom-out reduced card size while retaining the canvas-wide branch spread. Source preview, Escape exit, focus restoration, and wheel panning were verified.
- Temporary preview files and extracted private source data were removed after verification. The original PDF and backend generation pipeline were unchanged.

Evidence: `mind_map_canvas_browser.json`, `mind_map_canvas_frontend.log`, `mind_map_canvas_build.log`, `mind_map_canvas_lint.log`, and the default/fullscreen/phone screenshots in this directory.
