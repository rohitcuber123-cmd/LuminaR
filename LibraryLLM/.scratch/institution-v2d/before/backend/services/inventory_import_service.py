"""Retired legacy dataset writer; canonical imports use library_inventory_import."""
from backend.platform_dependencies import retirement
from backend.database.mongodb import inventory_preview_collection, library_inventory_collection

def create_preview(library_id,filename,file_bytes):
    retirement()

def confirm_inventory_import(preview_id,library_id):
    retirement()
