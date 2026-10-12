# Full state / API / helper inventory

| Module | Exports | Dependencies | Uses | Purpose / decision |
| --- | --- | --- | --- | --- |
| frontend/src/api/core.ts | api, dateValue | ../lib/api |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/hooks/useAssistantPageContext.ts | useAssistantPageContext | react, react-router-dom, ../store/useAssistantStore, ../lib/assistantTypes | useLocation, useEffect, useAssistantStore.getState().setPageContext, useAssistantStore.getState | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/hooks/useBookActionState.ts | useBookActionState | ../store/useAuthStore, ../lib/api | useAuthStore | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/hooks/useDeviceDocuments.ts | useDeviceDocuments | react, ../lib/api, ../lib/localDocumentCache, ../lib/documentCacheApi | useState, useRef, useCallback, useEffect | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/hooks/useLibraryCatalogue.ts | useLibraryCatalogue | react, ../store/useInstitutionStore, ../store/useAuthStore, ../lib/api, ../lib/libraryCatalogue, ../lib/catalogueInvalidation | useInstitutionStore, useAuthStore, useState, useEffect | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/hooks/useMoreLikeThis.ts | useMoreLikeThis | react, @/lib/api, @/lib/knowledgeGraph | useState, useRef, useCallback, useEffect | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/api.ts | BORROW_STATE_CHANGED, notifyBorrowChanged, getKnowMoreBooks, getReadableBook, getToken, request, login, register, verifyOTP, resendOTP, getBooks, getCategories, getBook, getPopularBooks, getNewArrivals, searchBooks, getSearchHistory, getRecommendations, sendRecommendationFeedback, getMyIssues, issueBook, returnBook, getMyReservations, reserveBook, cancelReservation, getMyFines, payFine, getMyActivity, getReadingList, addToReadingList, removeFromReadingList, getRAGDocuments, getRAGBooks, uploadRAGDocument, askRAG, getCoreHealth, getSearchHealth, getRAGHealth, coreRequest, staffLogin |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/assistant.ts | MAX_SELECTION_MESSAGE, validWorkId, uniqueIds, displayText, recommendLabel, recommendAction, recommendationHeading, sanitizePageContext, recentIds, assistantChat | ./api.ts, ./assistantTypes.ts |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/assistantTypes.ts |  | ./knowledgeGraph |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/authDestination.ts | destination, workspaceDestination |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/catalogueInvalidation.ts | CATALOGUE_CHANGED, catalogueChanged, observeCatalogue |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/documentCacheApi.ts | documentCacheScope, listDeviceCopies, keepDocumentOnDevice, restoreDeviceCopy, removeServerDocument, finishDocumentLogout | ./api, ./localDocumentCache |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/eventPresets.ts | EVENT_PRESETS, EVENT_PUBLISH_REQUIREMENTS, publishErrors, baseErrors, requiresPublishedValidation | ../../../backend/schemas/event_publish_requirements.json, ./events |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/events.ts | categories, EVENTS_CHANGED, eventApi, eventDate, author, eventDelta | ./api |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/institutions.ts | institutionApi, invitationLink | ./api |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/knowledgeArtifacts.ts | listArtifacts, generateArtifact, getSource, gradeCloze | ./api |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/knowledgeGraph.ts | graphMeta, graphBooks, graphRecommend, relatedBooks | ./api |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/libraryCatalogue.ts | catalogueBase, globalDisplayBook, loadCatalogue | ./api, ./institutions, ./libraryLending |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/libraryInventory.ts | inventoryBase, uploadInventory, commitInventory | ./api, ./institutions, ./libraryLending, ./catalogueInvalidation |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/libraryLending.ts | lendingBase, commandKey, withdrawLibraryBook, lendingCommand | ./institutions, ./api |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/libraryReservationsFees.ts | money, minorAmount |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/libraryWorkspace.ts | patronPath, patronLibraryIdFromPath, luminarHomePath, staffPath, workspacePath, membershipLabel, libraryRole, isLibraryStaff, libraryWorkspaceHome | ./institutions |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/loanRenewal.ts |  |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/localDocumentCache.ts | localDocumentCache |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/menuKeyboard.ts | menuKeys | react |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/nav.ts | getRoleNavLinks |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/notifications.ts | noticeDelta |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/ragAnswerMarkdown.ts | normalizeRAGMarkdown | unified, remark-parse, mdast |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/readNow.ts | readNowState, createReadNowOperation |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/searchPaging.ts | SEARCH_PAGE_SIZE, searchPaging, changeSearchContext |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/sessionStorageSync.ts | watchSessionStorage |  |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/lib/useInView.ts | useInView | react | useRef, useState, useEffect | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/store/useAssistantStore.ts | useAssistantStore | zustand, ../lib/api.ts, ../lib/assistant.ts, ../lib/assistantTypes.ts, ./useInstitutionStore.ts | useInstitutionStore.getState | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/store/useAuthStore.ts | useAuthStore | ../lib/documentCacheApi, ./useAssistantStore, zustand, ./useLibraryStore, ./useInstitutionStore, ../lib/api | useLibraryStore.getState().clearUserData, useLibraryStore.getState, useInstitutionStore.getState().reset, useInstitutionStore.getState, useAssistantStore.getState().syncOwner, useAssistantStore.getState | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/store/useEventStore.ts | useEventStore | zustand |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/store/useInstitutionStore.ts | useInstitutionStore, activeLibrary, patronLibrary, staffLibrary, patronCatalogueDestination | zustand, ../lib/institutions, ../lib/libraryWorkspace | useInstitutionStore.getState | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/store/useLibraryStore.ts | useLibraryStore | zustand, ../lib/api |  | REVIEW_REQUIRED; shared identity and URL context audited below |
| frontend/src/store/usePlatformStore.ts | usePlatformStore, platformAdmin | zustand, ../lib/api |  | REVIEW_REQUIRED; shared identity and URL context audited below |
