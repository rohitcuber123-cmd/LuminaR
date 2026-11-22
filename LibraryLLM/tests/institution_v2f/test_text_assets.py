from io import BytesIO
from zipfile import ZipFile
import hashlib
import pytest
from fastapi import HTTPException
from backend.services.library_asset_text import extract_text

def docx(text='Cedar Reading Room opens at 09:00.'):
    stream = BytesIO()
    with ZipFile(stream, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:body></w:document>')
    return stream.getvalue()

@pytest.mark.parametrize('kind,content', [('TXT', b'Cedar Reading Room opens at 09:00. <script>inert</script>'), ('DOCX', docx())])
def test_text_upload_preview_download_and_member_boundary(client, library, upload, ready, kind, content):
    lib = library()
    asset = upload(lib, filename='safe.'+kind.lower(), content=content).json()
    assert asset['asset_type'] == kind and asset['status'] == 'PROCESSING'
    base = f'/libraries/{lib}/assets/{asset["asset_id"]}'
    assert client.get(base+'/preview').status_code == 409
    ready(asset)
    assert client.get(base+'/preview').json()['text'].startswith('Cedar Reading Room')
    file = client.get(base+'/file')
    assert hashlib.sha256(file.content).hexdigest() == asset['checksum']
    assert file.headers['content-type'].startswith(asset['media_type'])
    assert client.get(base+'/preview', headers={'x-test-user':'2'}).status_code == 404
    assert client.post(f'/libraries/{lib}/join', headers={'x-test-user':'2'}, json={}).status_code == 200
    assert client.get(base+'/preview', headers={'x-test-user':'2'}).status_code == 200
    client.patch(base, json={'visibility':'STAFF_ONLY'})
    assert client.get(base+'/preview', headers={'x-test-user':'2'}).status_code == 404
    assert client.get(base+'/file', headers={'x-test-user':'2'}).status_code == 404

@pytest.mark.parametrize('kind,content', [('TXT', b'\xff\x00'), ('DOCX', b'not a zip'), ('DOCX', docx('&bad;')), ('TXT', b' '), ('TXT', b'x'*(8*1024*1024+1))], ids=['binary', 'bad-zip', 'invalid-xml', 'empty', 'oversize'])
def test_text_rejects_binary_invalid_empty_and_oversize(kind, content):
    with pytest.raises(HTTPException): extract_text(content, kind)

def test_legacy_doc_rejected(library, upload):
    assert upload(library(), filename='legacy.doc', content=b'legacy').status_code == 400

def test_pdf_source_page_visible_integrity_and_authorization(client, library, upload, ready):
    lib = library(); asset = upload(lib).json(); ready(asset)
    base = f'/libraries/{lib}/assets/{asset["asset_id"]}'
    image = client.get(base+'/preview/pages/1')
    assert image.status_code == 200 and image.content.startswith(b'\x89PNG')
    assert image.headers['content-type'] == 'image/png'
    assert client.get(base+'/preview/pages/0').status_code == 404
    assert client.get(base+'/preview/pages/999').status_code == 404
    assert client.get(base+'/preview/pages/1',headers={'x-test-user':'2'}).status_code == 404
    from backend.services import library_asset_service as service
    service.source_path(asset).write_bytes(b'changed')
    assert client.get(base+'/preview/pages/1').status_code == 409


def docx_xml(body):
    stream = BytesIO()
    with ZipFile(stream, 'w') as package:
        package.writestr('[Content_Types].xml', '<Types/>')
        package.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+body+'</w:body></w:document>')
    return stream.getvalue()


def test_docx_preserves_visible_run_separators_and_paragraphs():
    content = docx_xml('<w:p><w:r><w:t>Capacity</w:t><w:tab/><w:t>25</w:t><w:br/><w:t>Open</w:t><w:cr/><w:t>Monday</w:t></w:r></w:p><w:p><w:r><w:t>Next paragraph.</w:t></w:r></w:p>')
    assert extract_text(content, 'DOCX') == 'Capacity\t25\nOpen\nMonday\nNext paragraph.'


def test_docx_excludes_deleted_moved_and_field_instruction_text():
    content = docx_xml('<w:p><w:del><w:r><w:delText>Capacity 900.</w:delText></w:r></w:del><w:moveFrom><w:r><w:t>Capacity 800.</w:t></w:r></w:moveFrom><w:r><w:instrText>INCLUDETEXT external-file</w:instrText></w:r><w:ins><w:r><w:t>Capacity 25.</w:t></w:r></w:ins></w:p>')
    assert extract_text(content, 'DOCX') == 'Capacity 25.'


def test_docx_deleted_only_document_has_no_readable_source():
    with pytest.raises(HTTPException) as error:
        extract_text(docx_xml('<w:del><w:p><w:r><w:delText>Withdrawn fact.</w:delText></w:r></w:p></w:del>'), 'DOCX')
    assert error.value.status_code == 400


def test_docx_hyperlinks_field_results_and_table_paragraphs_are_visible():
    content = docx_xml('<w:p>\n <w:hyperlink><w:r><w:t>Visible link.</w:t></w:r></w:hyperlink><w:r><w:instrText>REF bookmark</w:instrText></w:r><w:r><w:t>Visible result.</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell text.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    assert extract_text(content, 'DOCX') == 'Visible link.Visible result.\nCell text.'
