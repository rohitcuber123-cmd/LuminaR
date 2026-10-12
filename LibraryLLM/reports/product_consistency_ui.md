# Product consistency verification

PASS. Shared global Header now has equal grid side tracks around the intrinsic navigation width; it no longer centers relative to unequal logo/account content. The maximum measured desktop center error is 0.00488 CSS pixels. Below 1280px, the navigation uses the existing keyboard-accessible drawer. Global, Patron, Staff and isolated Platform shells pass the six-size matrix.

All nine Staff headings start at x=263.984px and use 34px type at the desktop target. Shared heading gap is 20px, content padding is 24px/32px with bottom clearance, and common cards/forms retain the paper/rust/ink design. Sidebar rows are 44px with 17px icons. Inventory and Circulation filters now have the same 44px control height. Numeric metrics use 30px type; setup statuses use a compact 12px badge, not numeric typography. Fresh empty libraries show zero counts and usable actions without LEGACY, snapshot or activation warnings.

Operational Activity reports inventory/circulation/reservation/fee operations. ADMIN Audit / Activity explains its security, membership and administrative scope. Repeated workspace labels were removed from the main heading; sidebar identity and the two-part breadcrumb provide context.

The actual workspace root now applies the 52px assistant launcher with z-index 40 and safe-area offset. Native modal dialogs occupy the top layer; mobile confirmation controls remain visible and 44px high. Catalogue rails scroll by keyboard and use horizontal overflow/snap for pointer/touch use. Escape restores header-menu focus. Full accessibility certification and physical touch-device testing are outside this local audit.

Evidence: product_consistency_header.json, product_consistency_staff_geometry.json, product_consistency_interactions.json, and 144 loaded/actual-size browser cases. Saved PNGs use the host's 125% DPI backing pixels; actual CSS viewport sizes and one-pixel rounding are recorded separately. Earlier stale-handle and loading captures were replaced, with attempt history retained.
