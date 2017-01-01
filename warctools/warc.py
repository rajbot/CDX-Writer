"""An object to represent warc records, using the abstract record in record.py"""

import re
import base64
import hashlib
from .record import ArchiveRecord,ArchiveParser
from .archive_detect import register_record_type

bad_lines = 5 # when to give up looking for the version stamp

@ArchiveRecord.HEADERS(
    DATE='WARC-Date',
    TYPE = 'WARC-Type',
    ID = 'WARC-Record-ID',
    CONCURRENT_TO = 'WARC-Concurrent-To',
    REFERS_TO = 'WARC-Refers-To',
    CONTENT_LENGTH = 'Content-Length',
    CONTENT_TYPE = 'Content-Type',
    URL='WARC-Target-URI',
    BLOCK_DIGEST='WARC-Block-Digest',
    IP_ADDRESS='WARC-IP-Address',
    FILENAME='WARC-Filename',
    WARCINFO_ID='WARC-Warcinfo-ID',
    PAYLOAD_DIGEST = 'WARC-Payload-Digest',
)
class WarcRecord(ArchiveRecord):
    VERSION="WARC/1.0"
    VERSION18="WARC/0.18"
    VERSION17="WARC/0.17"
    RESPONSE="response"
    REQUEST="request"
    METADATA="metadata"
    CONVERSION="conversion"
    WARCINFO="warcinfo"

    def __init__(self, version=VERSION, headers=None, content=None, errors=None):
        ArchiveRecord.__init__(self,headers,content,errors)
        self.version = version

    @property
    def id(self):
        return self.get_header(self.ID)

    def _write_to(self, out, nl):
        """WARC Format:
            VERSION NL
            (Key: Value NL)*
            NL
            CONTENT NL
            NL

            don't write multi line headers
        """
        out.write(self.version)
        out.write(nl)
        for k,v in self.headers:
            if k not in (self.CONTENT_TYPE, self.CONTENT_LENGTH, self.BLOCK_DIGEST):
                out.write(k)
                out.write(": ")
                out.write(v)
                out.write(nl)
        content_type, content_buffer = self.content
        content_buffer=buffer(content_buffer)
        if content_type:
            out.write(self.CONTENT_TYPE)
            out.write(": ")
            out.write(content_type)
            out.write(nl)
        if content_buffer is None:
            content_buffer=""

        content_length = len(content_buffer)
        out.write(self.CONTENT_LENGTH)
        out.write(": ")
        out.write(str(content_length))
        out.write(nl)

        block_hash = hashlib.sha256()
        block_hash.update(content_buffer)

        digest= "sha256:%s"%block_hash.hexdigest()

        out.write(self.BLOCK_DIGEST)
        out.write(": ")
        out.write(digest)
        out.write(nl)

        # end of header blank nl
        out.write(nl)
        if content_buffer:
            out.write(content_buffer[:content_length])
        out.write(nl)
        out.write(nl)
        out.flush()

    def repair(self):
        pass

    def validate(self):
        return self.errors

    @classmethod
    def make_parser(self):
        return WarcParser()

def rx(pat):
    return re.compile(pat,flags=re.IGNORECASE)

version_rx = rx(r'^(?P<prefix>.*?)(?P<version>\s*WARC/(?P<number>.*?))' '(?P<nl>\r\n|\r|\n)\\Z')
# a header is key: <ws> value plus any following lines with leading whitespace
header_rx = rx(r'^(?P<name>.*?):\s?(?P<value>.*?)' '(?P<nl>\r\n|\r|\n)\\Z')
value_rx = rx(r'^\s+(?P<value>.+?)' '(?P<nl>\r\n|\r|\n)\\Z')
nl_rx=rx('^(?P<nl>\r\n|\r|\n\\Z)')
length_rx = rx('^'+WarcRecord.CONTENT_LENGTH+'$')
type_rx = rx('^'+WarcRecord.CONTENT_TYPE+'$')

required_headers = set((
    WarcRecord.TYPE.lower(),
    WarcRecord.ID.lower(),
    WarcRecord.CONTENT_LENGTH.lower(),
    WarcRecord.DATE.lower(),
))

class WarcParser(ArchiveParser):
    KNOWN_VERSIONS=set(('1.0', '0.17', '0.18'))
    def __init__(self):
        self.trailing_newlines = 0

    def parse(self,stream, offset):
        """Reads a warc record from the stream, returns a tuple (record, errors).
        Either records is null or errors is null. Any record-specific errors are
        contained in the record - errors is only used when *nothing* could be parsed"""
        errors = []
        version = None
        # find WARC/.*
        line = stream.readline()
        newlines = self.trailing_newlines
        if newlines > 0:
            while line:
                match = nl_rx.match(line)
                if match and newlines > 0:
                    if offset is not None: offset+=len(line)
                    newlines-=1
                    if match.group('nl') != '\x0d\x0a':
                        errors.append(('incorrect trailing newline', match.group('nl')))
                    line = stream.readline()
                    if newlines == 0:
                        break
                else:
                    break

            if newlines > 0:
                errors+=('less than two terminating newlines at end of previous record, missing', newlines)

        while line:
            match = version_rx.match(line)

            if match:
                version = match.group('version')
                if offset is not None: offset+=len(match.group('prefix'))
                break
            else:
                if offset is not None: offset+=len(line)
                if not nl_rx.match(line):
                    errors.append(('ignored line', line))
                    if len(errors) > bad_lines:
                        errors.append(('too many errors, giving up hope',))
                        return (None,errors, offset)
                line = stream.readline()
        if not line:
            if version:
                errors.append('warc version but no headers', version)
            self.trailing_newlines = 0
            return (None, errors, offset)
        if line:
            content_length = 0
            content_type = None

            record = WarcRecord(errors=errors, version=version)


            if match.group('nl') != '\x0d\x0a':
                record.error('incorrect newline in version', match.group('nl'))

            if match.group('number') not in self.KNOWN_VERSIONS:
                record.error('version field is not known (%s)'%(",".join(self.KNOWN_VERSIONS)), match.group('number'))


            prefix = match.group('prefix')

            if prefix:
                record.error('bad prefix on WARC version header', prefix)

            #Read headers
            line = stream.readline()
            while line and not nl_rx.match(line):

                #print 'header', repr(line)
                match = header_rx.match(line)
                if match:
                    if match.group('nl') != '\x0d\x0a':
                        record.error('incorrect newline in header', match.group('nl'))
                    name = match.group('name').strip()
                    value = [match.group('value').strip()]
                    #print 'match',name, value

                    line = stream.readline()
                    match = value_rx.match(line)
                    while match:
                        #print 'follow', repr(line)
                        if match.group('nl') != '\x0d\x0a':
                            record.error('incorrect newline in follow header',line, match.group('nl'))
                        value.append(match.group('value').strip())
                        line = stream.readline()
                        match = value_rx.match(line)

                    value = " ".join(value)

                    if type_rx.match(name):
                        if value:
                            content_type = value
                        else:
                            record.error('invalid header',name,value)
                    elif length_rx.match(name):
                        try:
                            #print name, value
                            content_length = int(value)
                            #print content_length
                        except ValueError:
                            record.error('invalid header',name,value)
                    else:
                        record.headers.append((name,value))

            # have read blank line following headers

            # read content

            ### rajbot: if the WARC-Payload-Digest is not present, fabricate it.
            ### We do this because we don't want to read large records into memory,
            ### since this was exhasting memory and crashing for large payloads.
            sha1_digest = None
            if 'response' == record.type and re.match('^application/http;\s*msgtype=response$', content_type):
                parsed_http_header = False
                digest = record.get_header(WarcRecord.PAYLOAD_DIGEST)
                if digest is None:
                    sha1_digest = hashlib.sha1()
            else:
                #This isn't a http response so pretend we already parsed the http header
                parsed_http_header = True

            if content_length is not None:
                if content_length > 0:
                    content=[]
                    length = 0

                    should_skip_content = False
                    if content_length > ArchiveParser.content_length_limit:
                        should_skip_content = True

                    while length < content_length:
                        if not parsed_http_header:
                            line = stream.readline()
                            #print 'header:', line
                        else:
                            bytes_to_read = min(content_length-length, 1024)
                            line = stream.read(bytes_to_read) #TODO: rename variable. may be more than just one line
                            #line = stream.readline()
                            #print 'line:', repr(line)
                        if not line:
                            #print 'no more data'
                            break

                        if should_skip_content:
                            if not parsed_http_header:
                                content.append(line)
                        else:
                            content.append(line)

                        length+=len(line)

                        if sha1_digest:
                            if parsed_http_header:
                                if length <= content_length:
                                    sha1_digest.update(line)
                                else:
                                    sha1_digest.update(line[:-(length-content_length)])

                        if not parsed_http_header:
                            if nl_rx.match(line):
                                parsed_http_header = True

                        #print length, content_length, line
                    #else:
                        # print 'last line of content', repr(line)
                    if sha1_digest:
                        sha1_str = 'sha1:'+base64.b32encode(sha1_digest.digest())
                        record.headers.append((WarcRecord.PAYLOAD_DIGEST, sha1_str))

                    content="".join(content)

                    if length > content_length:
                        #line is the last line we read
                        trailing_chars = line[-(length-content_length):]
                    else:
                        trailing_chars = ''

                    #content, line = content[0:content_length], content[content_length:]
                    content = content[0:content_length]

                    #if len(content)!= content_length:
                    if length < content_length:
                        record.error('content length mismatch (is, claims)', length, content_length)

                    record.content = (content_type, content)

                    if nl_rx.match(trailing_chars):
                        self.trailing_newlines = 1
                    else:
                        self.trailing_newlines = 2

            else:
                record.error('missing header', WarcRecord.CONTENT_LENGTH)
                self.trailing_newlines = 2

            # Fixed: READLINE BUG - eats trailing terminating newlines when content doesn't have a \n

            #print 'read content', repr(line)
            # have read trailing newlines

            # check mandatory headers
            #   WARC-Type
            #   WARC-Date WARC-Record-ID Content-Length

            # ignore mandatory newlines for now
            # because they are missing.
            # instead we trim a number of them off the next
            # parse

            # we can't re-wind easily without wrapping
            # every file handle

            # not brilliant but hey-ho




            return (record, (), offset)

    def trim(self, stream):
        """read the end of the file"""
        newlines = self.trailing_newlines
        self.trailing_newlines = 0
        errors = []
        if newlines:
            line = stream.readline()
            while line:
                #print 'trimming', repr(line)
                match = nl_rx.match(line)
                if match:
                    if match.group('nl') != '\x0d\x0a':
                        errors.append(('incorrect trailing newline', match.group('nl')))
                    newlines-=1
                    #print 'newline'
                    if newlines == 0:
                        break

                else:
                    #print 'line', line, newlines
                    newlines = 0
                    errors.append(('trailing data after content', line))
                line = stream.readline()
            if newlines > 0:
                errors+=('less than two terminating newlines at end of record, missing', newlines)

        return errors



blank_rx = rx(r'^$')
register_record_type(version_rx, WarcRecord)
register_record_type(blank_rx, WarcRecord)

def make_response(id, date, url, content, request_id):
    headers = [
            (WarcRecord.TYPE, WarcRecord.RESPONSE),
            (WarcRecord.ID, id),
            (WarcRecord.DATE, date),
            (WarcRecord.URL, url),

    ]
    if request_id:
        headers.append((WarcRecord.CONCURRENT_TO, request_id))

    record=WarcRecord(headers=headers, content=content)

    return record

def make_request(request_id, date, url, content, response_id):
    headers = [
            (WarcRecord.TYPE, WarcRecord.REQUEST),
            (WarcRecord.ID, request_id),
            (WarcRecord.DATE, date),
            (WarcRecord.URL, url),

    ]
    if response_id:
        headers.append((WarcRecord.CONCURRENT_TO, response_id))

    record=WarcRecord(headers=headers, content=content)

    return record

def make_metadata(meta_id, date, content, concurrent_to=None, url=None):
    headers = [
            (WarcRecord.TYPE, WarcRecord.METADATA),
            (WarcRecord.ID, meta_id),
            (WarcRecord.DATE, date),

    ]
    if concurrent_to:
        headers.append((WarcRecord.CONCURRENT_TO, concurrent_to))

    if url:
        headers.append((WarcRecord.URL, url))

    record=WarcRecord(headers=headers, content=content)

    return record


def make_conversion(conv_id, date, content, refers_to=None, url=None):
    headers = [
            (WarcRecord.TYPE, WarcRecord.CONVERSION),
            (WarcRecord.ID, conv_id),
            (WarcRecord.DATE, date),

    ]
    if refers_to:
        headers.append((WarcRecord.REFERS_TO, refers_to))

    if url:
        headers.append((WarcRecord.URL, url))

    record=WarcRecord(headers=headers, content=content)

    return record



def warc_datetime_str(d):
    s = d.isoformat()
    if '.' in s:
        s = s[:s.find('.')]
    return s +'Z'
