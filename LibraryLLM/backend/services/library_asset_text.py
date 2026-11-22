"""Bounded, inert TXT/DOCX extraction shared by upload, preview and processing."""
from io import BytesIO
from zipfile import ZipFile, BadZipFile
import xml.etree.ElementTree as ET
from fastapi import HTTPException

MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000


def docx_body_text(tree, ns):
    # Read displayed run text, not XML indentation, field instructions or
    # deleted/moved-from revisions. Preserve source word/line boundaries.
    parts = []
    stack = [(tree, False)]
    while stack:
        node, closing = stack.pop()
        if closing:
            parts.append('\n')
        elif node.tag in {ns + 'del', ns + 'moveFrom'}:
            continue
        elif node.tag == ns + 't':
            parts.append(node.text or '')
        elif node.tag == ns + 'tab':
            parts.append('\t')
        elif node.tag in {ns + 'br', ns + 'cr'}:
            parts.append('\n')
        else:
            if node.tag == ns + 'p':
                stack.append((node, True))
            stack.extend((child, False) for child in reversed(node))
    return ''.join(parts).removesuffix('\n')


def extract_text(content, kind):
    try:
        if kind == 'TXT':
            if len(content) > MAX_TEXT_BYTES:
                raise ValueError('Text file exceeds 8 MiB.')
            text = content.decode('utf-8-sig')
            if '\x00' in text:
                raise ValueError('Choose a UTF-8 text document.')
        elif kind == 'DOCX':
            with ZipFile(BytesIO(content)) as package:
                entries = package.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > 32 * 1024 * 1024:
                    raise ValueError('DOCX expanded content is too large.')
                names = [e.filename for e in entries]
                if names.count('word/document.xml') != 1 or '[Content_Types].xml' not in names:
                    raise ValueError('Choose a valid DOCX document.')
                entry = package.getinfo('word/document.xml')
                if entry.file_size > MAX_TEXT_BYTES or entry.flag_bits & 1:
                    raise ValueError('DOCX text is too large or encrypted.')
                xml = package.read(entry)
                if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
                    raise ValueError('DOCX declarations are unsupported.')
                tree = ET.fromstring(xml)
                ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                text = docx_body_text(tree, ns)
        else:
            raise ValueError('Unsupported text document.')
        if not text.strip() or len(text) > MAX_TEXT_CHARS:
            raise ValueError('Choose a readable document with at most 2 million characters.')
        return text
    except (ValueError, UnicodeError, BadZipFile, KeyError, ET.ParseError, RuntimeError) as error:
        raise HTTPException(400, str(error) if isinstance(error, ValueError) else 'The document could not be read.') from error
