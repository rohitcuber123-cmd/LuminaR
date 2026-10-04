"""Security events contain action, numeric IDs and timestamp only."""
import logging
logger = logging.getLogger('luminar.security')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(handler)

def security_event(action, actor_id=None, target_id=None):
    logger.info('action=%s actor_id=%s target_id=%s', action, actor_id, target_id)
