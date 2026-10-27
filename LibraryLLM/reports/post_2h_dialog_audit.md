# Post-Part-2H shared dialog audit

Intelligence already uses StaffUI.Modal. Its body was unwrapped and inherited `.institutions` typography; broad button rules colored/sized the close control like a CTA. No Intelligence-only modal or alternate modal stylesheet exists.

The repair adds one body wrapper, a 620px viewport-bounded width, 14px body, 22px heading, 44px neutral close target, shared actions, title association and aria-modal. Asset/add/edit bodies remove nested outer padding. Drawer/account variants retain their necessary geometry.

| File | Line | Classification | Rationale |
|---|---:|---|---|
| frontend/src/components/AccountMenu.tsx | 22 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/AIChatWidget.tsx | 155 | PAGE_SPECIFIC_NECESSARY | Non-modal assistant drawer, inline previous-document prompt, or fullscreen knowledge map; their specialized interaction is preserved. |
| frontend/src/components/CatalogueBookActions.tsx | 41 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/Header.tsx | 33 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/LibraryShells.tsx | 50 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/StaffBookManagement.tsx | 27 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/StaffBookManagement.tsx | 28 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/StaffUI.tsx | 153 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/StaffUI.tsx | 196 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/WorkspaceUI.tsx | 14 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/components/knowledge/KnowledgeMap.tsx | 124 | PAGE_SPECIFIC_NECESSARY | Non-modal assistant drawer, inline previous-document prompt, or fullscreen knowledge map; their specialized interaction is preserved. |
| frontend/src/components/knowledge/KnowledgeTools.tsx | 29 | PAGE_SPECIFIC_NECESSARY | Non-modal assistant drawer, inline previous-document prompt, or fullscreen knowledge map; their specialized interaction is preserved. |
| frontend/src/pages/EventEditorPage.tsx | 112 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/EventEditorPage.tsx | 113 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/InstitutionPanel.tsx | 82 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/InstitutionPanel.tsx | 86 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/InstitutionPanel.tsx | 87 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/Institutions.tsx | 100 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryAssets.tsx | 86 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryAssets.tsx | 116 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryAssets.tsx | 123 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryAssets.tsx | 291 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryCirculation.tsx | 162 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryIntelligence.tsx | 80 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryInventory.tsx | 122 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryInventory.tsx | 123 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryInventory.tsx | 124 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryReservationsFees.tsx | 89 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LibraryReservationsFees.tsx | 120 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/LLMPage.tsx | 1016 | PAGE_SPECIFIC_NECESSARY | Non-modal assistant drawer, inline previous-document prompt, or fullscreen knowledge map; their specialized interaction is preserved. |
| frontend/src/pages/ManageEventsPage.tsx | 28 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/PlatformAccounts.tsx | 86 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/PlatformAccounts.tsx | 95 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/PlatformConsole.tsx | 19 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/PlatformConsole.tsx | 54 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/PlatformConsole.tsx | 55 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/PlatformLibraries.tsx | 56 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/PlatformOperations.tsx | 77 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |
| frontend/src/pages/PlatformOperations.tsx | 136 | SHARED_ACCEPTED | StaffUI.Modal, shared tokens and body/close/action geometry. |

INTELLIGENCE_DUPLICATE: 0. OBSOLETE: 1 (legacy Staff.css base/header/heading/backdrop family retired). Build/Rebuild/Retry all pass content through the same Modal. Recovery-required uses existing card/status copy, with no separate dialog.
