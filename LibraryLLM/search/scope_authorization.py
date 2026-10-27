"""Fresh canonical authority and exact ownership-bound Search cleanup."""
from fastapi import HTTPException


def invalidate_if_access_lost(actor,library_id,*,staff=False):
    # A resource error or denial for STAFF cannot establish loss of PATRON.
    # Reuse the membership mutation lock so a role change cannot race between
    # fresh authorization evidence and deletion. Never change role policy.
    from backend.services.library_inventory_access import require_library_patron,require_library_staff
    from backend.services.identity_service import current_identity
    from search.session_store import invalidate_scope
    from search.personalization import invalidate_scope as invalidate_profile
    if not library_id:
        if current_identity(actor):return False
        invalidate_scope(actor);invalidate_profile(actor)
        return True
    from backend.services.institution_repository import library_mutation
    guards={False:require_library_patron,True:require_library_staff}
    def inaccessible(workspace):
        try:guards[workspace](library_id,actor,locked=True)
        except HTTPException as error:
            if error.status_code in (403,404):return True
            # Identity loss is independently confirmed, not inferred from401.
            if error.status_code==401 and not current_identity(actor):return True
            return False  # Busy/recovery is not authorization-loss evidence.
        return False
    try:
        with library_mutation(library_id,wait_seconds=3,durable=True):
            # Ordinary endpoint failures must stay side-effect free when the
            # requested workspace is still authorized.
            if not inaccessible(bool(staff)):return False
            for workspace in (False,True):
                if inaccessible(workspace):
                    invalidate_scope(actor,library_id,staff=workspace)
                    invalidate_profile(actor,library_id,staff=workspace)
            return True
    except HTTPException:
        # A lock/recovery failure defers cleanup; the original denial stands.
        return False
    return False
