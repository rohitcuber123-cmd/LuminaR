# Canonical communication authority

| Actor | Published reading | Draft/history reading | Create/edit/publish/withdraw/retry |
|---|---|---|---|
| Active library ADMIN (including owner) | Yes | Yes | Yes |
| Active LIBRARIAN | Yes | No | No new grant |
| Active GENERAL_USER | Yes | No | No |
| Admin of another library | No absent membership | No | No |
| Platform-only admin | No absent membership | No | No |
| Revoked/suspended/removed/invalid invitation proof | No | No | No |
| Private-code outsider | No | No | No |
| Disabled/unverified/password-setup-required account | No | No | No |

`library_announcement_service.access` uses eligible_actor/current_identity and the existing library membership/recovery boundary, then require_library_role('ADMIN') for management. No alternative role framework. Owner remains owner_user_id + ADMIN membership. Existing librarian Event permissions are unchanged.

All reads and domain mutations use the existing cross-worker library_mutation gate. Delivery takes the same gate for bounded recipient slices so membership revocation serializes with copying. Canonical resolution includes status ACTIVE and accepted invitation proof. Publication resolves eligible account identities in batches, not client-supplied recipient lists or account.role alone. The shared inbox filter uses the same membership, account, invitation and library lifecycle rules for only the new private type.

No production membership/account/role changes. Disposable fixtures may create distinct identities and institutions and revoke those owned fixtures to test access. Existing canonical transport and frozen authority fingerprints remain untouched.
