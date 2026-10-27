# 02 — LIBRARY CREATION, REGISTRATION & MEMBERSHIP LIFECYCLE

## 1. Library Creation & Registration Architecture

The creation of an independent institutional library in LuminaR is an authoritative, multi-step transaction executed within the backend Core API.

### 1.1 Complete Registration Flow Trace

```
   [ User Clicks "Register Library" ]
                   │
   Frontend: Institutions.tsx (Modal)
                   │
                   ▼
   API Request: POST /libraries/register
   Headers: Authorization: Bearer <JWT>
   Payload: { name, slug, description, access_mode, access_code, address, contact_email, phone }
                   │
                   ▼
   backend/routes/institutions.py: register(request, current_user=Depends(get_current_user))
                   │
                   ▼
   backend/services/institution_service.py: register_library(request, current_user)
                   │
                   ├── 1. Derives actor: user_id = actor_id(current_user) [FROM JWT SUB ONLY]
                   ├── 2. Generates canonical identifier: library_id = str(uuid4())
                   ├── 3. Normalizes slug: slug_normalized = data['slug'].lower()
                   ├── 4. Hashes access code (if provided): Argon2id via institution_security.py
                   ├── 5. Prepares membership: role = 'ADMIN', is_owner = True
                   │
                   ▼
   with library_mutation(library_id, durable=True): [DISTRIBUTED MONGO LOCK]
                   │
                   ├── Step A: Insert into institution_libraries with status: 'PROVISIONING'
                   │           (Traps DuplicateKeyError on unique slug_normalized)
                   ├── Step B: Insert into institution_security {'access_code_hash': Argon2id}
                   ├── Step C: Insert into institution_memberships {user_id, role: 'ADMIN'}
                   ├── Step D: Initialize canonical defaults: library_canonical_defaults.initialize_new()
                   ├── Step E: Record append-only audit event: 'LIBRARY_REGISTERED'
                   └── Step F: Update institution_libraries: status = 'ACTIVE'
                   │
                   ▼
   Response: 201 Created { library: public_library, membership: public_membership }
```

### 1.2 Code-Verified Analysis: Preventing Identity Spoofing

A critical security check is whether one user can register a library claiming another user is the owner:
- Code reference: [backend/services/institution_service.py:L58-65](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L58-L65):
  ```python
  def register_library(request, current_user):
      user_id = actor_id(current_user)
      library_id = str(uuid4())
      stamp = now()
      data = request.model_dump(mode='json', exclude={'access_code'})
      row = {**data, 'library_id': library_id, 'slug': data['slug'].lower(),
             'slug_normalized': data['slug'].lower(), 'owner_user_id': user_id,
             'status': 'PROVISIONING', 'created_at': stamp, 'updated_at': stamp}
  ```
- **Verification**: `owner_user_id` is assigned directly from `actor_id(current_user)`. The request schema (`RegisterLibrary`) forbids client-supplied `owner_user_id`. Any attempt to inject an owner ID in the JSON body is rejected by Pydantic schema validation (`extra='forbid'`).

### 1.3 The `PROVISIONING` Status Barrier

To prevent race conditions where a concurrent discovery query or worker observes a partially constructed library:
1. The record is inserted into `institution_libraries` with `status: 'PROVISIONING'` ([institution_service.py:L65](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L65)).
2. Discovery queries filter strictly on `status: 'ACTIVE'` ([institution_service.py:L89](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L89)).
3. Only after the security credentials, initial admin membership, and canonical default sequences are committed does the service flip status to `'ACTIVE'` ([institution_service.py:L83](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L83)).
4. If an unhandled exception crashes the process mid-provisioning, the library remains in `PROVISIONING` and is completely invisible to all users.

---

## 2. Access Modes and Entry Security

Institutions support two distinct visibility and access modes defined in `institution_models.py:AccessMode`:
1. `PUBLIC`: Open discovery; any authenticated platform user can join as a `GENERAL_USER`.
2. `PRIVATE_CODE`: Hidden entry; users must provide the institutional access passphrase to join.

### 2.1 Argon2id Passphrase Protection

When a private library is registered or its code rotated:
- Code reference: [backend/services/institution_security.py:L10-26](file:///d:/SDC/LibraryLLM/backend/services/institution_security.py#L10-L26):
  ```python
  hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)

  def hash_code(code):
      # Case-sensitive passphrases: do not trim or normalize human secrets.
      if not isinstance(code, str) or not 8 <= len(code) <= 128:
          raise ValueError('Access code must contain 8 to 128 characters.')
      return hasher.hash(code)

  def verify_code(encoded, code):
      if not encoded or not isinstance(code, str) or len(code) > 128:
          return False
      try:
          return hasher.verify(encoded, code)
      except (VerificationError, InvalidHashError, TypeError):
          return False
  ```
- **Algorithm**: `Argon2id` using parameters recommended by RFC 9106 (Low Memory Profile), providing high resistance against GPU/ASIC brute-force cracking.
- **Passphrase Constraints**: Minimum 8 characters, maximum 128 characters.
- **Credential Storage Isolation**: The access code hash is stored in a separate collection `institution_security` ([institution_repository.py:L26](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L26)), never in `institution_libraries`. Public library serialization functions completely omit security documents.

### 2.2 Rate-Limiting Brute-Force Budget (`consume_join_budget`)

To prevent online dictionary attacks against private access codes:
- Code reference: [backend/services/institution_service.py:L130-146](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L130-L146):
  ```python
  def consume_join_budget(library_id, user_id):
      stamp = now()
      window = max(60, int(os.getenv('LUMINAR_JOIN_WINDOW_SECONDS', '900')))
      bucket = int(stamp.timestamp()) // window
      for scope, cap in ((f'user:{user_id}:{library_id}', int(os.getenv('LUMINAR_JOIN_ATTEMPTS', '5'))),
                         (f'library:{library_id}', int(os.getenv('LUMINAR_LIBRARY_JOIN_ATTEMPTS', '200')))):
          key = f'{scope}:{bucket}'
          row = collection('attempts').find_one_and_update({'_id': key}, {
              '$inc': {'count': 1}, '$setOnInsert': {'expires_at': stamp + timedelta(seconds=window * 2)},
          }, upsert=True, return_document=ReturnDocument.AFTER)
          if row['count'] > cap:
              retry = window - int(stamp.timestamp()) % window
              raise HTTPException(429, 'Too many join attempts. Please try again later.', headers={'Retry-After': str(retry)})
  ```
- **Per-User Bounding**: A single user is limited to **5 attempts per 15-minute window** (`LUMINAR_JOIN_ATTEMPTS = 5`).
- **Per-Library Bounding**: A library is globally capped at **200 attempts per 15-minute window** (`LUMINAR_LIBRARY_JOIN_ATTEMPTS = 200`), defeating distributed brute-force attempts from multiple accounts.
- **Automatic TTL Expiration**: MongoDB index on `institution_attempts` with `{'expireAfterSeconds': 0}` purges expired attempt buckets automatically.

---

## 3. Membership Lifecycle & Staff Invitations

### 3.1 Membership Schema & Roles

Every membership record in `institution_memberships` contains:
```json
{
  "membership_id": "c1f7a391-4d7a-42c1-840a-115f0d38e091",
  "library_id": "a93e5022-722a-43cf-8a21-4f114c0a5d4a",
  "user_id": 1,
  "role": "ADMIN",
  "status": "ACTIVE",
  "joined_at": "2026-10-13T12:00:00Z",
  "created_at": "2026-10-13T12:00:00Z",
  "updated_at": "2026-10-13T12:00:00Z",
  "created_by_user_id": 1,
  "grant_invitation_id": null,
  "role_changed_by_user_id": null
}
```

### 3.2 Staff Invitation Security Protocol

Staff members (`ADMIN`, `LIBRARIAN`) cannot be added via public codes. They must be explicitly invited by an existing administrator.

```
   [ Library Admin ] invites user by email
             │
   POST /libraries/{library_id}/invitations { email, role: "LIBRARIAN" }
             │
             ├── 1. Validates Admin authority: require_library_role(library_id, current_user, 'ADMIN')
             ├── 2. Generates CSPRNG token: raw = secrets.token_urlsafe(32) [256 bits entropy]
             ├── 3. Hashes token: token_hash = sha256(raw)
             ├── 4. Inserts into institution_invitations:
             │      { invitation_id, library_id, email_normalized, role, token_hash, status: 'PENDING', expires_at: now + 7d }
             └── 5. Returns raw token ONCE in HTTP response { invitation, invite_token: raw }
                    (Raw token is NEVER saved in DB, NEVER echoed in list/audit/error endpoints)
```

### 3.3 Invitation Redemption & Anti-Privilege Escalation

When an invited user redeems the invitation:
- Code reference: [backend/services/institution_service.py:L300-338](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L300-L338):
  1. **Token Verification**: User provides the raw token. Backend computes `token_hash(token)` and matches against `institution_invitations`.
  2. **Account Email Binding**: The accepting user's verified account email (`users_collection`) must match `invitation.email_normalized`. One user cannot redeem an invitation issued to someone else's email address ([institution_service.py:L288-291](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L288-L291)).
  3. **Re-validation of Inviter Authority**:
     ```python
     # Stale invitations cannot preserve privileges after their inviter loses authority.
     inviter = {'sub': str(row['invited_by_user_id'])}
     require_library_role(library_id, inviter, 'ADMIN', locked=True)
     ```
     If the admin who created the invitation was subsequently revoked or demoted, **the invitation is immediately rejected**. A former admin cannot leave "backdoor" invitations.
  4. **Cryptographic Proof Binding**: When accepted, the membership record stores `grant_invitation_id = invitation_id`. The guard in [institution_dependencies.py:L27-33](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L27-L33) checks that an `ACCEPTED` invitation proof exists in the database for that user. If the proof document is missing, the membership is invalidated.

---

## 4. Role Hierarchy & Administrative Safeguards

### 4.1 Implemented Roles

1. **Owner (`is_owner = True`)**: The user whose `user_id` matches `library.owner_user_id`. Immutable admin membership.
2. **Admin (`ADMIN`)**: Can manage inventory, digital assets, catalog intelligence builds, invitations, staff roles, and library settings.
3. **Librarian (`LIBRARIAN`)**: Can manage inventory, circulation approvals, return reviews, digital asset uploads, and catalog imports. Cannot invite admins or modify library security settings.
4. **General User / Patron (`GENERAL_USER`)**: Can view ready member assets, search the catalog, borrow books, reserve holdings, and view personal loans and fees.

### 4.2 Administrative Safeguards

1. **Owner Protection**: The library owner's membership can never be demoted, suspended, or removed ([institution_service.py:L325, L381](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L325#L381)):
   ```python
   if target['user_id'] == library['owner_user_id']:
       raise HTTPException(403, 'Owner membership cannot be changed.')
   ```
2. **Last Admin Protection**: An admin cannot demote themselves or another admin if they are the last active admin ([institution_service.py:L390-392](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L390-L392)):
   ```python
   if collection('memberships').count_documents({'library_id': library_id, 'role': 'ADMIN', 'status': 'ACTIVE'}) <= 1:
       raise HTTPException(409, 'At least one active admin must remain.')
   ```
3. **Owner-Only Admin Delegation**: Only the owner can invite or elevate other users to `ADMIN` ([institution_service.py:L229-232](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L229-L232)):
   ```python
   def check_staff_policy(library, current_user, target_role):
       if target_role == 'ADMIN' and library['owner_user_id'] != actor_id(current_user):
           raise HTTPException(403, 'Only the owner may manage admins.')
   ```
4. **Platform Admin Non-Interference**: Global platform administrators (`PLATFORM_ADMIN`) do not inherit library tenant authority. Attempting to manage a library without an explicit tenant membership record returns `404 Not Found` ([tests/institution_v2h/test_controls.py:L20-22](file:///d:/SDC/LibraryLLM/tests/institution_v2h/test_controls.py#L20-L22)).

---

## 5. Security Summary for Viva Defense

- **Creation Identity**: Guaranteed by JWT `sub` extraction; client cannot specify `owner_user_id`.
- **Passphrase Security**: Argon2id RFC 9106 low memory profile; brute force blocked by dual-scope bucketed rate limiter.
- **Invite Security**: 256-bit CSPRNG tokens, stored as SHA256 hashes, single-use, bound to verified email, invalidated if the inviter loses admin rights.
- **Guaranteed Isolation**: Revocation is immediate because membership is evaluated dynamically on every request rather than stored in JWT claims.
