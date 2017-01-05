from __future__ import unicode_literals
import sys
import py
sys.path[0:0] = (str(py.path.local(__file__) / '../..'),)

import pytest
import hashlib
import base64

import io
from gzip import GzipFile
from cdx_writer import CDX_Writer
from hanzo.warctools import WarcRecord

def create_metadata_record_bytes(
    url='http://example.com/',
    content_type='image/png',
    date='2016-08-03T10:49:41Z',
    content=b'',
    include_block_digest=True):
    """Build WARC metadata record bits."""

    headers = {
        WarcRecord.TYPE: WarcRecord.METADATA,
        WarcRecord.URL: url.encode('utf-8'),
        WarcRecord.CONTENT_TYPE: content_type.encode('utf-8'),
        WarcRecord.DATE: date.encode('utf-8')
        }
    if include_block_digest:
        hasher = hashlib.sha1(content)
        block_digest = base64.b32encode(hasher.digest())
        headers[WarcRecord.BLOCK_DIGEST] = b'sha1:' + block_digest

    # XXX - I wish I could use WarcRecord. Current implementation of
    # WarcRecord.write_to() ignores Warc-Block-Digest passed and writes out
    # hex-encoded SHA256 calculated from the content.
    out = io.BytesIO()
    if False:
        rec = WarcRecord(
            headers=headers.items(),
            content=(content_type.encode('utf-8'), content)
            )
        out = io.BytesIO()
        rec.write_to(out, gzip=True)
        return out.getvalue()
    else:
        z = GzipFile(fileobj=out, mode='wb')
        z.write(b'WARC/1.0\r\n')
        for k, v in headers.items():
            z.write(b''.join((k, b': ', v, b'\r\n')))
        z.write('Content-Length: {}\r\n'.format(len(content)).encode('ascii'))
        z.write(b'\r\n')
        z.write(content)
        z.write(b'\r\n\r\n')
        z.flush()
        z.close()
        return out.getvalue()

@pytest.mark.parametrize("block_digest", [ True, False ])
def test_sceenshot_regular(block_digest, tmpdir):
    """IA-proprietary screen capture archive format:
    PNG image is archived as ``metadata`` record. ``Content-Type`` is
    ``image/png``, and SHA1 digest is in ``WARC-Block-Digest``.
    data block is the screen capture image itself.

    If record has no WARC-Block_Digest (block_digest==False), CDX_Writer shall
    compute SHA1 digest on its own.
    """
    # fake screenshot data
    payload = b'\x01' * 128
    payload_digest = base64.b32encode(hashlib.sha1(payload).digest())

    recbits = create_metadata_record_bytes(content=payload, include_block_digest=block_digest)
    warc = tmpdir / 'test.warc.gz'
    warc.write(recbits, mode='wb')
    reclen = len(recbits)

    cdxout = tmpdir / 'test.cdx'
    with tmpdir.as_cwd():
        cdx_writer = CDX_Writer(warc.basename, cdxout.basename, screenshot_mode=True)
        cdx_writer.make_cdx()

    assert cdxout.isfile()
    cdx =  cdxout.readlines() # utf-8 decoded
    assert len(cdx) == 2
    cdx1 = cdx[1].rstrip().split(' ')
    assert cdx1 == [
        'com,example)/',
        '20160803104941',
        'http://web.archive.org/screenshot/http://example.com/',
        'image/png',
        '-', # statuscode is undefined
        payload_digest,
        '-', '-',
        format(reclen), '0',
        warc.basename
        ]
