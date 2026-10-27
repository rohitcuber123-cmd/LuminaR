# Route entry
RoutePresentation animates the existing content node with opacity and a 6px translate over 200ms on pathname changes only. It uses native Web Animations and never keys/remounts routes to animate. Query, filter, pagination and local form updates do not replay it. Auth and assistant screens now expose the same main content landmark.
New paths start at top; query changes preserve position; POP restores stored entry position, including async layout restoration. Hash navigation and pagination use the sticky-header offset helper. Reduced motion skips entry animation.
